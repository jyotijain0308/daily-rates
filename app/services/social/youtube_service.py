"""YouTube OAuth and MP4 upload helpers."""
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

import requests
from flask import current_app, url_for

from app.models import SocialConnection
from wsgi import db


YOUTUBE_PROVIDER = 'youtube'
YOUTUBE_UPLOAD_SCOPE = 'https://www.googleapis.com/auth/youtube.upload'
YOUTUBE_CHANNEL_READ_SCOPE = 'https://www.googleapis.com/auth/youtube.readonly'
GOOGLE_AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'
YOUTUBE_CHANNELS_URL = 'https://www.googleapis.com/youtube/v3/channels'
YOUTUBE_UPLOAD_URL = 'https://www.googleapis.com/upload/youtube/v3/videos'


class YouTubeConfigError(RuntimeError):
    """Raised when YouTube OAuth settings are missing."""


class YouTubePublishError(RuntimeError):
    """Raised when YouTube upload fails."""


def _client_id():
    return os.getenv('YOUTUBE_CLIENT_ID', '').strip()


def _client_secret():
    return os.getenv('YOUTUBE_CLIENT_SECRET', '').strip()


def youtube_config_ready():
    return bool(_client_id() and _client_secret())


def youtube_redirect_uri():
    configured = os.getenv('YOUTUBE_REDIRECT_URI', '').strip()
    if configured:
        return configured
    return url_for('social.youtube_callback', _external=True)


def _require_config():
    if not youtube_config_ready():
        raise YouTubeConfigError(
            'Set YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET before connecting YouTube.'
        )


def _connection(company_id):
    return SocialConnection.query.filter_by(
        company_id=company_id,
        provider=YOUTUBE_PROVIDER,
    ).first()


def get_youtube_connection(company_id):
    return _connection(company_id)


def create_youtube_authorization_url(company_id):
    """Create a Google OAuth URL and store the expected state."""
    _require_config()
    state = f'{company_id}:{uuid.uuid4().hex}'
    connection = _connection(company_id)
    if not connection:
        connection = SocialConnection(company_id=company_id, provider=YOUTUBE_PROVIDER)
        db.session.add(connection)

    connection.oauth_state = state
    db.session.commit()

    params = {
        'client_id': _client_id(),
        'redirect_uri': youtube_redirect_uri(),
        'response_type': 'code',
        'scope': f'{YOUTUBE_UPLOAD_SCOPE} {YOUTUBE_CHANNEL_READ_SCOPE}',
        'access_type': 'offline',
        'prompt': 'consent',
        'include_granted_scopes': 'true',
        'state': state,
    }
    return f'{GOOGLE_AUTH_URL}?{urlencode(params)}'


def exchange_youtube_code(code, state):
    """Exchange a Google OAuth code and store the resulting YouTube connection."""
    _require_config()
    company_id = int((state or '').split(':', 1)[0])
    connection = _connection(company_id)
    if not connection or connection.oauth_state != state:
        raise YouTubePublishError('Invalid YouTube connection state. Start the connection again.')

    response = requests.post(
        GOOGLE_TOKEN_URL,
        data={
            'code': code,
            'client_id': _client_id(),
            'client_secret': _client_secret(),
            'redirect_uri': youtube_redirect_uri(),
            'grant_type': 'authorization_code',
        },
        timeout=30,
    )
    token_data = _json_or_error(response, 'Could not connect YouTube account')
    _store_tokens(connection, token_data)

    try:
        channel = fetch_youtube_channel(connection)
        connection.external_account_id = channel.get('id')
        connection.external_account_name = channel.get('title')
    except YouTubePublishError:
        # Upload scope may still be valid even if channel lookup fails.
        pass

    connection.oauth_state = None
    connection.connected_at = datetime.utcnow()
    db.session.commit()
    return connection


def disconnect_youtube(company_id):
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
    expires_in = int(token_data.get('expires_in') or 3600)
    connection.token_expires_at = datetime.utcnow() + timedelta(seconds=max(0, expires_in - 60))


def access_token(connection):
    """Return a valid access token, refreshing if needed."""
    if not connection or not connection.is_connected():
        raise YouTubePublishError('YouTube is not connected for this company.')

    if connection.access_token and connection.token_expires_at and connection.token_expires_at > datetime.utcnow():
        return connection.access_token

    if not connection.refresh_token:
        raise YouTubePublishError('YouTube refresh token is missing. Reconnect YouTube.')

    response = requests.post(
        GOOGLE_TOKEN_URL,
        data={
            'client_id': _client_id(),
            'client_secret': _client_secret(),
            'refresh_token': connection.refresh_token,
            'grant_type': 'refresh_token',
        },
        timeout=30,
    )
    token_data = _json_or_error(response, 'Could not refresh YouTube access token')
    _store_tokens(connection, token_data)
    db.session.commit()
    return connection.access_token


def fetch_youtube_channel(connection):
    token = access_token(connection)
    response = requests.get(
        YOUTUBE_CHANNELS_URL,
        headers={'Authorization': f'Bearer {token}'},
        params={'part': 'snippet', 'mine': 'true'},
        timeout=30,
    )
    data = _json_or_error(response, 'Could not read YouTube channel')
    items = data.get('items') or []
    if not items:
        raise YouTubePublishError('No YouTube channel found for the connected Google account.')

    item = items[0]
    return {
        'id': item.get('id'),
        'title': (item.get('snippet') or {}).get('title'),
    }


def upload_video(connection, file_path, title, description='', privacy_status='private'):
    """Upload a generated MP4 to the connected YouTube channel."""
    token = access_token(connection)
    path = Path(file_path)
    if not path.exists():
        raise YouTubePublishError('Generated MP4 file was not found.')
    if path.suffix.lower() != '.mp4':
        raise YouTubePublishError('Only MP4 files can be published to YouTube.')

    resource = {
        'snippet': {
            'title': title[:100],
            'description': description or '',
            'categoryId': '22',
        },
        'status': {
            'privacyStatus': privacy_status if privacy_status in {'private', 'unlisted', 'public'} else 'private',
            'selfDeclaredMadeForKids': False,
        },
    }
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json; charset=UTF-8',
        'X-Upload-Content-Length': str(path.stat().st_size),
        'X-Upload-Content-Type': 'video/mp4',
    }
    init_response = requests.post(
        YOUTUBE_UPLOAD_URL,
        headers=headers,
        params={'uploadType': 'resumable', 'part': 'snippet,status'},
        json=resource,
        timeout=30,
    )
    if init_response.status_code not in {200, 201} or not init_response.headers.get('Location'):
        _json_or_error(init_response, 'Could not initialize YouTube upload')
        raise YouTubePublishError('Could not initialize YouTube upload.')

    with path.open('rb') as video_file:
        upload_response = requests.put(
            init_response.headers['Location'],
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': 'video/mp4',
                'Content-Length': str(path.stat().st_size),
            },
            data=video_file,
            timeout=600,
        )

    data = _json_or_error(upload_response, 'Could not upload video to YouTube')
    video_id = data.get('id')
    if not video_id:
        raise YouTubePublishError('YouTube upload completed without a video id.')

    return {
        'video_id': video_id,
        'url': f'https://www.youtube.com/watch?v={video_id}',
        'title': data.get('snippet', {}).get('title') or title,
        'privacy_status': data.get('status', {}).get('privacyStatus') or privacy_status,
    }


def _json_or_error(response, fallback_message):
    try:
        data = response.json()
    except ValueError:
        data = {}

    if response.ok:
        return data

    error = data.get('error') or {}
    if isinstance(error, dict):
        message = error.get('message') or fallback_message
    else:
        message = str(error) or fallback_message
    raise YouTubePublishError(message)
