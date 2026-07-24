"""TikTok OAuth and MP4 draft upload helpers."""
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

import requests
from flask import url_for

from app.models import SocialConnection
from wsgi import db


TIKTOK_PROVIDER = 'tiktok'
TIKTOK_AUTH_URL = 'https://www.tiktok.com/v2/auth/authorize/'
TIKTOK_TOKEN_URL = 'https://open.tiktokapis.com/v2/oauth/token/'
TIKTOK_USER_INFO_URL = 'https://open.tiktokapis.com/v2/user/info/'
TIKTOK_UPLOAD_INIT_URL = 'https://open.tiktokapis.com/v2/post/publish/inbox/video/init/'
TIKTOK_DEFAULT_SCOPES = ('user.info.basic', 'video.upload')
TIKTOK_UPLOAD_CHUNK_SIZE = 64 * 1024 * 1024


class TikTokConfigError(RuntimeError):
    """Raised when TikTok app settings are missing."""


class TikTokPublishError(RuntimeError):
    """Raised when TikTok connection or upload fails."""


def _client_key():
    return os.getenv('TIKTOK_CLIENT_KEY', '').strip()


def _client_secret():
    return os.getenv('TIKTOK_CLIENT_SECRET', '').strip()


def _scopes():
    configured = os.getenv('TIKTOK_SCOPES', '').strip().strip('"').strip("'")
    if configured:
        return tuple(
            scope.strip().strip('"').strip("'")
            for scope in configured.replace(',', ' ').split()
            if scope.strip()
        )
    return TIKTOK_DEFAULT_SCOPES


def tiktok_config_ready():
    return bool(_client_key() and _client_secret())


def tiktok_redirect_uri():
    configured = os.getenv('TIKTOK_REDIRECT_URI', '').strip()
    if configured:
        return configured
    return url_for('social.tiktok_callback', _external=True)


def _require_config():
    if not tiktok_config_ready():
        raise TikTokConfigError(
            'Set TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET before connecting TikTok.'
        )


def _connection(company_id):
    return SocialConnection.query.filter_by(
        company_id=company_id,
        provider=TIKTOK_PROVIDER,
    ).first()


def get_tiktok_connection(company_id):
    return _connection(company_id)


def create_tiktok_authorization_url(company_id):
    """Create a TikTok OAuth URL and store the expected state."""
    _require_config()
    state = f'{company_id}:{uuid.uuid4().hex}'
    connection = _connection(company_id)
    if not connection:
        connection = SocialConnection(company_id=company_id, provider=TIKTOK_PROVIDER)
        db.session.add(connection)

    connection.oauth_state = state
    db.session.commit()

    params = {
        'client_key': _client_key(),
        'response_type': 'code',
        'scope': ','.join(_scopes()),
        'redirect_uri': tiktok_redirect_uri(),
        'state': state,
    }
    return f'{TIKTOK_AUTH_URL}?{urlencode(params)}'


def exchange_tiktok_code(code, state):
    """Exchange a TikTok OAuth code and store the resulting connection."""
    _require_config()
    company_id = int((state or '').split(':', 1)[0])
    connection = _connection(company_id)
    if not connection or connection.oauth_state != state:
        raise TikTokPublishError('Invalid TikTok connection state. Start the connection again.')

    response = requests.post(
        TIKTOK_TOKEN_URL,
        data={
            'client_key': _client_key(),
            'client_secret': _client_secret(),
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': tiktok_redirect_uri(),
        },
        headers={'Content-Type': 'application/x-www-form-urlencoded', 'Cache-Control': 'no-cache'},
        timeout=30,
    )
    token_data = _json_or_error(response, 'Could not connect TikTok account')
    _store_tokens(connection, token_data)
    connection.external_account_id = token_data.get('open_id')

    try:
        profile = fetch_tiktok_profile(connection.access_token)
        connection.external_account_name = profile.get('display_name') or profile.get('open_id')
    except TikTokPublishError:
        connection.external_account_name = connection.external_account_id

    connection.oauth_state = None
    connection.connected_at = datetime.utcnow()
    db.session.commit()
    return connection


def disconnect_tiktok(company_id):
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


def _store_tokens(connection, token_data):
    connection.access_token = token_data.get('access_token')
    if token_data.get('refresh_token'):
        connection.refresh_token = token_data['refresh_token']
    expires_in = int(token_data.get('expires_in') or 86400)
    connection.token_expires_at = datetime.utcnow() + timedelta(seconds=max(0, expires_in - 60))


def access_token(connection):
    """Return a valid TikTok access token, refreshing if needed."""
    if not connection or not connection.is_connected():
        raise TikTokPublishError('TikTok is not connected for this company.')

    if connection.access_token and connection.token_expires_at and connection.token_expires_at > datetime.utcnow():
        return connection.access_token

    if not connection.refresh_token:
        raise TikTokPublishError('TikTok refresh token is missing. Reconnect TikTok.')

    response = requests.post(
        TIKTOK_TOKEN_URL,
        data={
            'client_key': _client_key(),
            'client_secret': _client_secret(),
            'grant_type': 'refresh_token',
            'refresh_token': connection.refresh_token,
        },
        headers={'Content-Type': 'application/x-www-form-urlencoded', 'Cache-Control': 'no-cache'},
        timeout=30,
    )
    token_data = _json_or_error(response, 'Could not refresh TikTok access token')
    _store_tokens(connection, token_data)
    db.session.commit()
    return connection.access_token


def fetch_tiktok_profile(token):
    response = requests.get(
        TIKTOK_USER_INFO_URL,
        headers={'Authorization': f'Bearer {token}'},
        params={'fields': 'open_id,display_name,avatar_url'},
        timeout=30,
    )
    data = _json_or_error(response, 'Could not read TikTok profile')
    return (data.get('data') or {}).get('user') or {}


def upload_video_draft(connection, file_path):
    """Upload an MP4 draft to TikTok Inbox for the user to finish posting."""
    token = access_token(connection)
    path = Path(file_path)
    if not path.exists():
        raise TikTokPublishError('Generated MP4 file was not found.')
    if path.suffix.lower() != '.mp4':
        raise TikTokPublishError('Only MP4 files can be uploaded to TikTok.')

    size = path.stat().st_size
    if size <= 0:
        raise TikTokPublishError('Generated MP4 file is empty.')

    chunk_size = min(size, TIKTOK_UPLOAD_CHUNK_SIZE)
    total_chunk_count = (size + chunk_size - 1) // chunk_size
    init_response = requests.post(
        TIKTOK_UPLOAD_INIT_URL,
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json; charset=UTF-8',
        },
        json={
            'source_info': {
                'source': 'FILE_UPLOAD',
                'video_size': size,
                'chunk_size': chunk_size,
                'total_chunk_count': total_chunk_count,
            },
        },
        timeout=30,
    )
    init_data = _json_or_error(init_response, 'Could not initialize TikTok upload')
    upload_data = init_data.get('data') or {}
    publish_id = upload_data.get('publish_id')
    upload_url = upload_data.get('upload_url')
    if not publish_id or not upload_url:
        raise TikTokPublishError('TikTok upload initialization did not return an upload URL.')

    with path.open('rb') as video_file:
        start = 0
        while start < size:
            chunk = video_file.read(chunk_size)
            if not chunk:
                break
            end = start + len(chunk) - 1
            upload_response = requests.put(
                upload_url,
                headers={
                    'Content-Type': 'video/mp4',
                    'Content-Length': str(len(chunk)),
                    'Content-Range': f'bytes {start}-{end}/{size}',
                },
                data=chunk,
                timeout=600,
            )
            if upload_response.status_code not in {200, 201, 202, 204}:
                _json_or_error(upload_response, 'Could not upload video to TikTok')
                raise TikTokPublishError('Could not upload video to TikTok.')
            start = end + 1

    return {
        'publish_id': publish_id,
        'url': '',
        'status': 'uploaded',
    }


def _json_or_error(response, fallback_message):
    try:
        data = response.json()
    except ValueError:
        data = {}

    error = data.get('error') if isinstance(data, dict) else None
    error_code = (error or {}).get('code')
    if not response.ok or (error_code and error_code != 'ok'):
        message = (
            (error or {}).get('message')
            or data.get('error_description')
            or data.get('message')
            or fallback_message
        )
        raise TikTokPublishError(message)
    return data
