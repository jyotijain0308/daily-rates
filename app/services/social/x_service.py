"""X OAuth and MP4 Post publishing helpers."""
import base64
import hashlib
import os
import secrets
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

import requests
from flask import url_for

from app.models import SocialConnection
from app.services.social.app_config_service import get_social_app_value
from wsgi import db


X_PROVIDER = 'x'
X_AUTH_URL = 'https://x.com/i/oauth2/authorize'
X_TOKEN_URL = 'https://api.x.com/2/oauth2/token'
X_USER_ME_URL = 'https://api.x.com/2/users/me'
X_MEDIA_UPLOAD_URL = 'https://api.x.com/2/media/upload'
X_MEDIA_INITIALIZE_URL = 'https://api.x.com/2/media/upload/initialize'
X_TWEETS_URL = 'https://api.x.com/2/tweets'
X_DEFAULT_SCOPES = ('tweet.read', 'tweet.write', 'users.read', 'media.write', 'offline.access')
X_UPLOAD_CHUNK_SIZE = 5 * 1024 * 1024
X_MAX_POST_TEXT_LENGTH = 280


class XConfigError(RuntimeError):
    """Raised when X app settings are missing."""


class XPublishError(RuntimeError):
    """Raised when X connection, upload, or publishing fails."""


def _client_id():
    return get_social_app_value(X_PROVIDER, 'client_id', 'X_CLIENT_ID')


def _client_secret():
    return get_social_app_value(X_PROVIDER, 'client_secret', 'X_CLIENT_SECRET')


def _scopes():
    configured = get_social_app_value(X_PROVIDER, 'scopes', 'X_SCOPES').strip('"').strip("'")
    if configured:
        return tuple(
            scope.strip().strip('"').strip("'")
            for scope in configured.replace(',', ' ').split()
            if scope.strip()
        )
    return X_DEFAULT_SCOPES


def x_config_ready():
    return bool(_client_id())


def x_redirect_uri():
    configured = get_social_app_value(X_PROVIDER, 'redirect_uri', 'X_REDIRECT_URI')
    if configured:
        return configured
    return url_for('social.x_callback', _external=True)


def _require_config():
    if not x_config_ready():
        raise XConfigError('Set X_CLIENT_ID before connecting X.')


def _connection(company_id):
    return SocialConnection.query.filter_by(
        company_id=company_id,
        provider=X_PROVIDER,
    ).first()


def get_x_connection(company_id):
    return _connection(company_id)


def create_x_authorization_url(company_id):
    """Create an X OAuth 2.0 PKCE URL and store expected state and verifier."""
    _require_config()
    state = f'{company_id}:{secrets.token_urlsafe(18)}'
    verifier = secrets.token_urlsafe(48)
    connection = _connection(company_id)
    if not connection:
        connection = SocialConnection(company_id=company_id, provider=X_PROVIDER)
        db.session.add(connection)

    connection.oauth_state = f'{state}:{verifier}'
    db.session.commit()

    challenge = _pkce_challenge(verifier)
    params = {
        'response_type': 'code',
        'client_id': _client_id(),
        'redirect_uri': x_redirect_uri(),
        'scope': ' '.join(_scopes()),
        'state': state,
        'code_challenge': challenge,
        'code_challenge_method': 'S256',
    }
    return f'{X_AUTH_URL}?{urlencode(params)}'


def exchange_x_code(code, state):
    """Exchange X OAuth code and store the resulting connection."""
    _require_config()
    company_id = int((state or '').split(':', 1)[0])
    connection = _connection(company_id)
    expected_state, verifier = _oauth_state_parts(connection)
    if expected_state != state:
        raise XPublishError('Invalid X connection state. Start the connection again.')

    response = requests.post(
        X_TOKEN_URL,
        data={
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': x_redirect_uri(),
            'client_id': _client_id(),
            'code_verifier': verifier,
        },
        headers=_token_headers(),
        auth=_client_auth(),
        timeout=30,
    )
    token_data = _json_or_error(response, 'Could not connect X account')
    _store_tokens(connection, token_data)

    try:
        profile = fetch_x_profile(connection.access_token)
        connection.external_account_id = profile.get('id')
        username = profile.get('username')
        connection.external_account_name = f'@{username}' if username else profile.get('name')
    except XPublishError:
        pass

    connection.oauth_state = None
    connection.connected_at = datetime.utcnow()
    db.session.commit()
    return connection


def disconnect_x(company_id):
    connection = _connection(company_id)
    if not connection:
        return None

    connection.access_token = None
    connection.refresh_token = None
    connection.token_expires_at = None
    connection.external_account_id = None
    connection.external_account_name = None
    connection.oauth_state = None
    connection.connected_at = None
    db.session.commit()
    return connection


def access_token(connection):
    """Return a valid X access token, refreshing if needed."""
    if not connection or not connection.is_connected():
        raise XPublishError('X is not connected for this company.')

    if connection.access_token and connection.token_expires_at and connection.token_expires_at > datetime.utcnow():
        return connection.access_token

    if not connection.refresh_token:
        raise XPublishError('X refresh token is missing. Reconnect X.')

    response = requests.post(
        X_TOKEN_URL,
        data={
            'grant_type': 'refresh_token',
            'refresh_token': connection.refresh_token,
            'client_id': _client_id(),
        },
        headers=_token_headers(),
        auth=_client_auth(),
        timeout=30,
    )
    token_data = _json_or_error(response, 'Could not refresh X access token')
    _store_tokens(connection, token_data)
    db.session.commit()
    return connection.access_token


def fetch_x_profile(token):
    response = requests.get(
        X_USER_ME_URL,
        headers={'Authorization': f'Bearer {token}'},
        params={'user.fields': 'id,name,username'},
        timeout=30,
    )
    data = _json_or_error(response, 'Could not read X profile')
    return data.get('data') or {}


def publish_video_post(connection, file_path, text):
    """Upload an MP4 to X and publish a Post containing the uploaded media."""
    token = access_token(connection)
    path = Path(file_path)
    if not path.exists():
        raise XPublishError('Generated MP4 file was not found.')
    if path.suffix.lower() != '.mp4':
        raise XPublishError('Only MP4 files can be published to X.')
    if path.stat().st_size <= 0:
        raise XPublishError('Generated MP4 file is empty.')

    media_id = upload_video_media(token, path)
    post = create_post(token, _trim_post_text(text), media_id)
    post_id = post.get('id')
    if not post_id:
        raise XPublishError('X created the Post without returning a Post id.')
    username = (connection.external_account_name or '').lstrip('@')
    return {
        'post_id': post_id,
        'url': f'https://x.com/{username}/status/{post_id}' if username else f'https://x.com/i/web/status/{post_id}',
        'text': post.get('text') or text,
        'media_id': media_id,
    }


def upload_video_media(token, path):
    size = path.stat().st_size
    init_response = requests.post(
        X_MEDIA_INITIALIZE_URL,
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json; charset=UTF-8',
        },
        json={
            'media_type': 'video/mp4',
            'total_bytes': size,
            'media_category': get_social_app_value(
                X_PROVIDER,
                'media_category',
                'X_MEDIA_CATEGORY',
                'tweet_video',
            ) or 'tweet_video',
        },
        timeout=30,
    )
    media_data = (_json_or_error(init_response, 'Could not initialize X media upload').get('data') or {})
    media_id = media_data.get('id')
    if not media_id:
        raise XPublishError('X media upload did not return a media id.')

    with path.open('rb') as video_file:
        segment_index = 0
        while True:
            chunk = video_file.read(X_UPLOAD_CHUNK_SIZE)
            if not chunk:
                break
            append_response = requests.post(
                f'{X_MEDIA_UPLOAD_URL}/{media_id}/append',
                headers={'Authorization': f'Bearer {token}'},
                data={'segment_index': str(segment_index)},
                files={'media': ('chunk.mp4', chunk, 'video/mp4')},
                timeout=600,
            )
            if append_response.status_code not in {200, 201, 202, 204}:
                _json_or_error(append_response, 'Could not upload video chunk to X')
                raise XPublishError('Could not upload video chunk to X.')
            segment_index += 1

    finalize_response = requests.post(
        f'{X_MEDIA_UPLOAD_URL}/{media_id}/finalize',
        headers={'Authorization': f'Bearer {token}'},
        timeout=30,
    )
    if finalize_response.status_code in {404, 405}:
        finalize_response = requests.post(
            X_MEDIA_UPLOAD_URL,
            headers={'Authorization': f'Bearer {token}'},
            data={'command': 'FINALIZE', 'media_id': media_id},
            timeout=30,
        )
    finalize_data = _json_or_error(finalize_response, 'Could not finalize X media upload')
    _wait_for_processing(token, media_id, (finalize_data.get('data') or {}).get('processing_info'))
    return media_id


def create_post(token, text, media_id):
    response = requests.post(
        X_TWEETS_URL,
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json; charset=UTF-8',
        },
        json={
            'text': text,
            'media': {'media_ids': [media_id]},
        },
        timeout=30,
    )
    data = _json_or_error(response, 'Could not publish Post to X')
    return data.get('data') or {}


def _wait_for_processing(token, media_id, processing_info=None):
    info = processing_info or {}
    attempts = 0
    while info and info.get('state') in {'pending', 'in_progress'}:
        if attempts >= 30:
            raise XPublishError('X media processing did not finish in time.')
        time.sleep(max(1, int(info.get('check_after_secs') or 1)))
        status_response = requests.get(
            X_MEDIA_UPLOAD_URL,
            headers={'Authorization': f'Bearer {token}'},
            params={'command': 'STATUS', 'media_id': media_id},
            timeout=30,
        )
        status_data = _json_or_error(status_response, 'Could not check X media processing status')
        info = (status_data.get('data') or {}).get('processing_info') or {}
        attempts += 1

    if info and info.get('state') == 'failed':
        error = info.get('error') or {}
        raise XPublishError(error.get('message') or 'X media processing failed.')


def _store_tokens(connection, token_data):
    connection.access_token = token_data.get('access_token')
    if token_data.get('refresh_token'):
        connection.refresh_token = token_data['refresh_token']
    expires_in = int(token_data.get('expires_in') or 7200)
    connection.token_expires_at = datetime.utcnow() + timedelta(seconds=max(0, expires_in - 60))


def _oauth_state_parts(connection):
    if not connection or not connection.oauth_state:
        raise XPublishError('Invalid X connection state. Start the connection again.')
    parts = connection.oauth_state.split(':', 2)
    if len(parts) != 3:
        raise XPublishError('Invalid X connection state. Start the connection again.')
    return ':'.join(parts[:2]), parts[2]


def _pkce_challenge(verifier):
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b'=').decode()


def _client_auth():
    secret = _client_secret()
    if not secret:
        return None
    return (_client_id(), secret)


def _token_headers():
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Cache-Control': 'no-cache',
    }
    if _client_secret():
        return headers
    headers['Authorization'] = 'Basic ' + base64.b64encode(f'{_client_id()}:'.encode()).decode()
    return headers


def _trim_post_text(text):
    text = ' '.join(str(text or '').split())
    if not text:
        raise XPublishError('X Post text is required.')
    return text[:X_MAX_POST_TEXT_LENGTH]


def _json_or_error(response, fallback_message):
    try:
        data = response.json()
    except ValueError:
        data = {}

    errors = data.get('errors') if isinstance(data, dict) else None
    if not response.ok or errors:
        message = _response_error_message(data, fallback_message)
        if not message or message == fallback_message:
            raw_body = (response.text or '').strip()
            if raw_body:
                message = f'{fallback_message}: HTTP {response.status_code} {raw_body[:500]}'
            else:
                message = f'{fallback_message}: HTTP {response.status_code}'
        raise XPublishError(message)
    return data


def _response_error_message(data, fallback_message):
    if not isinstance(data, dict):
        return fallback_message
    errors = data.get('errors')
    if errors:
        first = errors[0]
        if isinstance(first, dict):
            return first.get('detail') or first.get('message') or first.get('title') or fallback_message
        return str(first)
    if isinstance(data.get('error'), dict):
        error = data['error']
        return error.get('message') or error.get('detail') or error.get('title') or fallback_message
    if data.get('detail'):
        return data['detail']
    if data.get('title'):
        return data['title']
    return data.get('error_description') or data.get('message') or data.get('error') or fallback_message
