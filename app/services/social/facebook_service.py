"""Facebook OAuth and Page video publishing helpers."""
import os
import sys
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

import requests
from flask import url_for

from app.models import SocialConnection
from wsgi import db


FACEBOOK_PROVIDER = 'facebook'
FACEBOOK_AUTH_BASE_URL = 'https://www.facebook.com'
FACEBOOK_GRAPH_BASE_URL = 'https://graph.facebook.com'
FACEBOOK_SCOPES = (
    'pages_show_list',
    'pages_read_engagement',
    'pages_manage_posts',
    'instagram_basic',
    'instagram_content_publish',
    'business_management',
)

# Backward-compatible import path for older tests that patch
# facebook_service.requests after importing this module by package path.
sys.modules.setdefault('facebook_service', sys.modules[__name__])


class FacebookConfigError(RuntimeError):
    """Raised when Facebook app settings are missing."""


class FacebookPublishError(RuntimeError):
    """Raised when Facebook connection or publishing fails."""


def _app_id():
    return os.getenv('FACEBOOK_APP_ID', '').strip()


def _app_secret():
    return os.getenv('FACEBOOK_APP_SECRET', '').strip()


def _graph_version():
    return (os.getenv('FACEBOOK_GRAPH_VERSION', '').strip() or 'v23.0').lstrip('/')


def _login_config_id():
    return os.getenv('FACEBOOK_LOGIN_CONFIG_ID', '').strip()


def _scopes():
    configured = os.getenv('FACEBOOK_SCOPES', '').strip()
    if configured:
        return tuple(scope.strip() for scope in configured.split(',') if scope.strip())
    return FACEBOOK_SCOPES


def facebook_config_ready():
    return bool(_app_id() and _app_secret())


def facebook_redirect_uri():
    configured = os.getenv('FACEBOOK_REDIRECT_URI', '').strip()
    if configured:
        return configured
    return url_for('social.facebook_callback', _external=True)


def _require_config():
    if not facebook_config_ready():
        raise FacebookConfigError(
            'Set FACEBOOK_APP_ID and FACEBOOK_APP_SECRET before connecting Facebook.'
        )


def _connection(company_id):
    return SocialConnection.query.filter_by(
        company_id=company_id,
        provider=FACEBOOK_PROVIDER,
    ).first()


def get_facebook_connection(company_id):
    return _connection(company_id)


def create_facebook_authorization_url(company_id):
    """Create a Facebook OAuth URL and store the expected state."""
    _require_config()
    state = f'{company_id}:{uuid.uuid4().hex}'
    connection = _connection(company_id)
    if not connection:
        connection = SocialConnection(company_id=company_id, provider=FACEBOOK_PROVIDER)
        db.session.add(connection)

    connection.oauth_state = state
    db.session.commit()

    params = {
        'client_id': _app_id(),
        'redirect_uri': facebook_redirect_uri(),
        'response_type': 'code',
        'state': state,
        'auth_type': 'rerequest',
    }
    config_id = _login_config_id()
    if config_id:
        params['config_id'] = config_id
        params['override_default_response_type'] = 'true'
    else:
        params['scope'] = ','.join(_scopes())
    return f'{FACEBOOK_AUTH_BASE_URL}/{_graph_version()}/dialog/oauth?{urlencode(params)}'


def exchange_facebook_code(code, state):
    """Exchange a Facebook OAuth code and store the first available Page connection."""
    _require_config()
    company_id = int((state or '').split(':', 1)[0])
    connection = _connection(company_id)
    if not connection or connection.oauth_state != state:
        raise FacebookPublishError('Invalid Facebook connection state. Start the connection again.')

    token_data = _exchange_code_for_token(code)
    user_token = _extend_user_token(token_data.get('access_token') or '')
    pages = fetch_facebook_pages(user_token)
    if not pages:
        raise FacebookPublishError('No Facebook Pages found for this account.')

    page = pages[0]
    connection.access_token = page['access_token']
    connection.refresh_token = user_token
    connection.token_expires_at = _token_expiry(token_data)
    connection.external_account_id = page['id']
    connection.external_account_name = page['name']
    connection.oauth_state = None
    connection.connected_at = datetime.utcnow()
    db.session.commit()
    return connection


def disconnect_facebook(company_id):
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


def fetch_facebook_pages(user_access_token):
    if not user_access_token:
        raise FacebookPublishError('Facebook user access token is missing. Reconnect Facebook.')

    response = requests.get(
        _graph_url('/me/accounts'),
        params={
            'access_token': user_access_token,
            'fields': 'id,name,access_token,tasks',
        },
        timeout=30,
    )
    data = _json_or_error(response, 'Could not read Facebook Pages')
    raw_pages = data.get('data') or []
    if not raw_pages:
        assigned_pages = fetch_assigned_facebook_pages(user_access_token)
        if assigned_pages:
            return assigned_pages

        granted_permissions = fetch_granted_permissions(user_access_token)
        raise FacebookPublishError(
            'No Facebook Pages were returned by Meta after checking /me/accounts and /me/assigned_pages. '
            'This usually means the Page is managed through Business Manager/task access or the user token '
            'does not include effective Page access. Grant business_management, pages_show_list, '
            f'pages_read_engagement, and pages_manage_posts, then disconnect and reconnect Facebook. '
            f'Granted permissions in this token: {", ".join(granted_permissions) or "none"}'
        )

    pages = []
    pages_missing_access_token = []
    for item in raw_pages:
        if item.get('id') and item.get('name') and item.get('access_token'):
            pages.append({
                'id': item['id'],
                'name': item['name'],
                'access_token': item['access_token'],
                'tasks': item.get('tasks') or [],
            })
        elif item.get('id') and item.get('name'):
            fallback_token = fetch_page_access_token(item['id'], user_access_token)
            if fallback_token:
                pages.append({
                    'id': item['id'],
                    'name': item['name'],
                    'access_token': fallback_token,
                    'tasks': item.get('tasks') or [],
                })
            else:
                pages_missing_access_token.append(item.get('name'))

    if not pages and pages_missing_access_token:
        raise FacebookPublishError(
            'Facebook Pages were selected, but Meta did not return Page access tokens for them. '
            'Grant pages_manage_posts and pages_read_engagement, make sure your Facebook user has '
            f'content/manage access to the Page, then disconnect and reconnect Facebook. Pages without tokens: '
            f'{", ".join(pages_missing_access_token)}'
        )
    return pages


def fetch_assigned_facebook_pages(user_access_token):
    """Fetch Pages assigned to a Business user when /me/accounts is empty."""
    response = requests.get(
        _graph_url('/me/assigned_pages'),
        params={
            'access_token': user_access_token,
            'fields': 'id,name,tasks',
        },
        timeout=30,
    )
    if not response.ok:
        return []

    data = response.json()
    pages = []
    for item in data.get('data') or []:
        page_id = item.get('id')
        page_name = item.get('name')
        if not page_id or not page_name:
            continue
        page_token = fetch_page_access_token(page_id, user_access_token)
        if not page_token:
            continue
        pages.append({
            'id': page_id,
            'name': page_name,
            'access_token': page_token,
            'tasks': item.get('tasks') or [],
        })
    return pages


def fetch_page_access_token(page_id, user_access_token):
    if not page_id or not user_access_token:
        return None

    response = requests.get(
        _graph_url(f'/{page_id}'),
        params={
            'access_token': user_access_token,
            'fields': 'access_token',
        },
        timeout=30,
    )
    if not response.ok:
        return None
    data = response.json()
    return data.get('access_token')


def fetch_granted_permissions(user_access_token):
    response = requests.get(
        _graph_url('/me/permissions'),
        params={'access_token': user_access_token},
        timeout=30,
    )
    if not response.ok:
        return []

    data = response.json()
    return sorted(
        item.get('permission')
        for item in data.get('data') or []
        if item.get('status') == 'granted' and item.get('permission')
    )


def upload_page_video(connection, file_path, title, description=''):
    """Upload a generated MP4 to the connected Facebook Page."""
    if not connection or not connection.is_connected():
        raise FacebookPublishError('Facebook Page is not connected for this company.')
    if not connection.external_account_id or not connection.access_token:
        raise FacebookPublishError('Facebook Page connection is incomplete. Reconnect Facebook.')

    path = Path(file_path)
    if not path.exists():
        raise FacebookPublishError('Generated MP4 file was not found.')
    if path.suffix.lower() != '.mp4':
        raise FacebookPublishError('Only MP4 files can be published to Facebook.')

    with path.open('rb') as video_file:
        response = requests.post(
            _graph_url(f'/{connection.external_account_id}/videos'),
            data={
                'access_token': connection.access_token,
                'title': title[:255],
                'description': description or title,
                'published': 'true',
            },
            files={'source': (path.name, video_file, 'video/mp4')},
            timeout=600,
        )

    data = _json_or_error(response, 'Could not upload video to Facebook Page')
    video_id = data.get('id')
    if not video_id:
        raise FacebookPublishError('Facebook upload completed without a video id.')

    return {
        'video_id': video_id,
        'url': f'https://www.facebook.com/watch/?v={video_id}',
        'title': title,
    }


def get_connected_instagram_account(connection):
    """Return the Instagram professional account linked to the connected Facebook Page."""
    if not connection or not connection.is_connected():
        raise FacebookPublishError('Facebook Page is not connected for this company.')
    if not connection.external_account_id or not connection.access_token:
        raise FacebookPublishError('Facebook Page connection is incomplete. Reconnect Facebook.')

    response = requests.get(
        _graph_url(f'/{connection.external_account_id}'),
        params={
            'access_token': connection.access_token,
            'fields': 'instagram_business_account{id,username,name}',
        },
        timeout=30,
    )
    data = _json_or_error(response, 'Could not read connected Instagram account')
    account = data.get('instagram_business_account') or {}
    if not account.get('id'):
        return None
    return {
        'id': account['id'],
        'username': account.get('username') or account.get('name') or account['id'],
        'name': account.get('name') or account.get('username') or account['id'],
    }


def upload_instagram_reel(connection, video_url, caption):
    """Publish an MP4 as an Instagram Reel through the linked Instagram account."""
    if not video_url:
        raise FacebookPublishError('Set SOCIAL_PUBLIC_BASE_URL so Instagram can fetch the generated MP4.')
    account = get_connected_instagram_account(connection)
    if not account:
        raise FacebookPublishError('No Instagram professional account is connected to the Facebook Page.')

    create_response = requests.post(
        _graph_url(f"/{account['id']}/media"),
        data={
            'access_token': connection.access_token,
            'media_type': 'REELS',
            'video_url': video_url,
            'caption': caption,
        },
        timeout=60,
    )
    create_data = _json_or_error(create_response, 'Could not create Instagram Reel container')
    creation_id = create_data.get('id')
    if not creation_id:
        raise FacebookPublishError('Instagram did not return a media container id.')

    _wait_for_instagram_container(connection, creation_id, video_url)

    publish_response = requests.post(
        _graph_url(f"/{account['id']}/media_publish"),
        data={
            'access_token': connection.access_token,
            'creation_id': creation_id,
        },
        timeout=60,
    )
    publish_data = _json_or_error(publish_response, 'Could not publish Instagram Reel')
    media_id = publish_data.get('id')
    if not media_id:
        raise FacebookPublishError('Instagram publish completed without a media id.')

    permalink = fetch_instagram_media_permalink(connection, media_id)
    return {
        'media_id': media_id,
        'container_id': creation_id,
        'url': permalink or _instagram_account_url(account),
        'account': account,
    }


def fetch_instagram_media_permalink(connection, media_id):
    if not media_id:
        return ''

    response = requests.get(
        _graph_url(f'/{media_id}'),
        params={
            'access_token': connection.access_token,
            'fields': 'permalink',
        },
        timeout=30,
    )
    if not response.ok:
        return ''
    data = response.json()
    return data.get('permalink') or ''


def _instagram_account_url(account):
    username = (account.get('username') or '').strip()
    if username and username != account.get('id'):
        return f'https://www.instagram.com/{username}/'
    return 'https://www.instagram.com/'


def _wait_for_instagram_container(connection, creation_id, video_url='', attempts=20, delay_seconds=3):
    for _attempt in range(attempts):
        response = requests.get(
            _graph_url(f'/{creation_id}'),
            params={
                'access_token': connection.access_token,
                'fields': 'status_code,status',
            },
            timeout=30,
        )
        data = _json_or_error(response, 'Could not read Instagram media container status')
        status_code = data.get('status_code')
        if status_code == 'FINISHED':
            return
        if status_code == 'ERROR':
            detail = data.get('status') or data.get('error_message') or ''
            message = 'Instagram could not process the MP4 container.'
            if detail:
                message = f'{message} Meta status: {detail}'
            if video_url:
                message = f'{message} Video URL: {video_url}'
            raise FacebookPublishError(message)
        time.sleep(delay_seconds)

    raise FacebookPublishError(
        'Instagram MP4 container was not ready to publish. Try again shortly.'
        + (f' Video URL: {video_url}' if video_url else '')
    )


def _exchange_code_for_token(code):
    response = requests.get(
        _graph_url('/oauth/access_token'),
        params={
            'client_id': _app_id(),
            'client_secret': _app_secret(),
            'redirect_uri': facebook_redirect_uri(),
            'code': code,
        },
        timeout=30,
    )
    return _json_or_error(response, 'Could not connect Facebook account')


def _extend_user_token(short_lived_token):
    if not short_lived_token:
        raise FacebookPublishError('Facebook did not return an access token.')

    response = requests.get(
        _graph_url('/oauth/access_token'),
        params={
            'grant_type': 'fb_exchange_token',
            'client_id': _app_id(),
            'client_secret': _app_secret(),
            'fb_exchange_token': short_lived_token,
        },
        timeout=30,
    )
    data = _json_or_error(response, 'Could not extend Facebook access token')
    return data.get('access_token') or short_lived_token


def _token_expiry(token_data):
    expires_in = token_data.get('expires_in')
    if not expires_in:
        return None
    return datetime.utcnow() + timedelta(seconds=max(0, int(expires_in) - 60))


def _graph_url(path):
    return f'{FACEBOOK_GRAPH_BASE_URL}/{_graph_version()}{path}'


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
    raise FacebookPublishError(message)
