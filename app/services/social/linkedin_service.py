"""LinkedIn OAuth and personal video publishing helpers."""
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

import requests
from flask import url_for

from app.models import SocialConnection
from app.services.social.app_config_service import get_social_app_value
from wsgi import db


LINKEDIN_PERSONAL_PROVIDER = 'linkedin_personal'
LINKEDIN_PAGE_PROVIDER = 'linkedin_page'
LINKEDIN_PROVIDER = LINKEDIN_PAGE_PROVIDER
LINKEDIN_AUTH_URL = 'https://www.linkedin.com/oauth/v2/authorization'
LINKEDIN_TOKEN_URL = 'https://www.linkedin.com/oauth/v2/accessToken'
LINKEDIN_USERINFO_URL = 'https://api.linkedin.com/v2/userinfo'
LINKEDIN_ORGANIZATION_ACLS_URL = 'https://api.linkedin.com/v2/organizationAcls'
LINKEDIN_ASSETS_URL = 'https://api.linkedin.com/v2/assets'
LINKEDIN_UGC_POSTS_URL = 'https://api.linkedin.com/v2/ugcPosts'
LINKEDIN_MEMBER_SCOPES = ('openid', 'profile', 'w_member_social')
LINKEDIN_ORGANIZATION_SCOPES = (
    'openid',
    'profile',
    'rw_organization_admin',
    'w_organization_social',
)


class LinkedInConfigError(RuntimeError):
    """Raised when LinkedIn app settings are missing."""


class LinkedInPublishError(RuntimeError):
    """Raised when LinkedIn connection or publishing fails."""


def _client_id():
    return get_social_app_value('linkedin', 'client_id', 'LINKEDIN_CLIENT_ID')


def _client_secret():
    return get_social_app_value('linkedin', 'client_secret', 'LINKEDIN_CLIENT_SECRET')


def _scopes(target):
    key = 'personal_scopes' if target == 'personal' else 'page_scopes'
    env_key = 'LINKEDIN_PERSONAL_SCOPES' if target == 'personal' else 'LINKEDIN_PAGE_SCOPES'
    configured = get_social_app_value('linkedin', key, env_key).strip('"').strip("'")
    if not configured and target == 'page':
        configured = os.getenv('LINKEDIN_SCOPES', '').strip().strip('"').strip("'")
    if configured:
        return tuple(
            scope.strip().strip('"').strip("'")
            for scope in configured.replace(',', ' ').split()
            if scope.strip()
        )
    if target == 'personal':
        return LINKEDIN_MEMBER_SCOPES
    return LINKEDIN_ORGANIZATION_SCOPES


def _prompt():
    return get_social_app_value('linkedin', 'prompt', 'LINKEDIN_PROMPT', 'login')


def _normalize_target(target):
    target = (target or '').strip().lower()
    if target in {'personal', 'member', 'profile'}:
        return 'personal'
    if target in {'page', 'organization', 'company'}:
        return 'page'
    raise LinkedInPublishError('Invalid LinkedIn target.')


def _provider(target):
    return LINKEDIN_PERSONAL_PROVIDER if _normalize_target(target) == 'personal' else LINKEDIN_PAGE_PROVIDER


def linkedin_config_ready():
    return bool(_client_id() and _client_secret())


def linkedin_publish_target():
    return 'page'


def linkedin_redirect_uri():
    configured = get_social_app_value('linkedin', 'redirect_uri', 'LINKEDIN_REDIRECT_URI')
    if configured:
        return configured
    return url_for('social.linkedin_callback', _external=True)


def _require_config():
    if not linkedin_config_ready():
        raise LinkedInConfigError(
            'Set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET before connecting LinkedIn.'
        )


def _connection(company_id, target='page'):
    return SocialConnection.query.filter_by(
        company_id=company_id,
        provider=_provider(target),
    ).first()


def get_linkedin_connection(company_id, target='page'):
    return _connection(company_id, target)


def create_linkedin_authorization_url(company_id, target='page'):
    """Create a LinkedIn OAuth URL and store the expected state."""
    _require_config()
    target = _normalize_target(target)
    state = f'{company_id}:{target}:{uuid.uuid4().hex}'
    connection = _connection(company_id, target)
    if not connection:
        connection = SocialConnection(company_id=company_id, provider=_provider(target))
        db.session.add(connection)

    connection.oauth_state = state
    db.session.commit()

    params = {
        'response_type': 'code',
        'client_id': _client_id(),
        'redirect_uri': linkedin_redirect_uri(),
        'scope': ' '.join(_scopes(target)),
        'state': state,
    }
    prompt = _prompt()
    if prompt:
        params['prompt'] = prompt
    return f'{LINKEDIN_AUTH_URL}?{urlencode(params)}'


def exchange_linkedin_code(code, state):
    """Exchange LinkedIn OAuth code and store the selected publishing identity."""
    _require_config()
    parts = (state or '').split(':', 2)
    if len(parts) == 3:
        company_id = int(parts[0])
        target = _normalize_target(parts[1])
    else:
        company_id = int((state or '').split(':', 1)[0])
        target = 'page'

    connection = _connection(company_id, target)
    if not connection or connection.oauth_state != state:
        raise LinkedInPublishError('Invalid LinkedIn connection state. Start the connection again.')

    response = requests.post(
        LINKEDIN_TOKEN_URL,
        data={
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': linkedin_redirect_uri(),
            'client_id': _client_id(),
            'client_secret': _client_secret(),
        },
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        timeout=30,
    )
    token_data = _json_or_error(response, 'Could not connect LinkedIn account')
    access_token = token_data.get('access_token')
    if not access_token:
        raise LinkedInPublishError('LinkedIn did not return an access token.')

    connection.access_token = access_token
    connection.refresh_token = token_data.get('refresh_token')
    connection.token_expires_at = _token_expiry(token_data)

    if target == 'personal':
        profile = fetch_linkedin_profile(access_token)
        member_id = profile.get('sub')
        if not member_id:
            raise LinkedInPublishError('LinkedIn profile response did not include a member id.')
        connection.external_account_id = member_id
        connection.external_account_name = profile.get('name') or member_id
    else:
        organizations = fetch_linkedin_organizations(access_token)
        if not organizations:
            raise LinkedInPublishError(
                'No LinkedIn Pages found. Connect with an account that is an admin of a LinkedIn Page.'
            )
        organization = organizations[0]
        connection.external_account_id = organization['id']
        connection.external_account_name = organization['name']

    connection.oauth_state = None
    connection.connected_at = datetime.utcnow()
    db.session.commit()
    return connection


def disconnect_linkedin(company_id, target='page'):
    connection = _connection(company_id, target)
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


def fetch_linkedin_profile(access_token):
    response = requests.get(
        LINKEDIN_USERINFO_URL,
        headers={'Authorization': f'Bearer {access_token}'},
        timeout=30,
    )
    return _json_or_error(response, 'Could not read LinkedIn profile')


def fetch_linkedin_organizations(access_token):
    response = requests.get(
        LINKEDIN_ORGANIZATION_ACLS_URL,
        headers=_rest_headers(access_token),
        params={
            'q': 'roleAssignee',
            'role': 'ADMINISTRATOR',
            'state': 'APPROVED',
            'projection': '(elements*(organization,organization~(localizedName)))',
        },
        timeout=30,
    )
    data = _json_or_error(response, 'Could not read LinkedIn Pages')
    organizations = []
    for item in data.get('elements') or []:
        organization_urn = item.get('organization') or ''
        organization_id = _urn_id(organization_urn)
        organization_info = item.get('organization~') or {}
        if organization_id:
            organizations.append({
                'id': organization_id,
                'name': organization_info.get('localizedName') or organization_id,
            })
    return organizations


def upload_video_post(connection, file_path, title, description='', visibility='PUBLIC', target='page'):
    """Upload an MP4 and publish it to the connected LinkedIn identity."""
    token = _valid_access_token(connection)
    owner_urn = _owner_urn(connection, target)
    path = Path(file_path)
    if not path.exists():
        raise LinkedInPublishError('Generated MP4 file was not found.')
    if path.suffix.lower() != '.mp4':
        raise LinkedInPublishError('Only MP4 files can be published to LinkedIn.')

    asset_urn, upload_url = _register_video_upload(token, owner_urn)
    _upload_video_asset(upload_url, path)
    post_urn = _create_video_post(token, owner_urn, asset_urn, title, description, visibility)
    return {
        'post_id': post_urn,
        'url': 'https://www.linkedin.com/feed/',
        'asset_urn': asset_urn,
        'title': title,
    }


def _valid_access_token(connection):
    if not connection or not connection.is_connected():
        raise LinkedInPublishError('LinkedIn is not connected for this company.')
    if not connection.access_token:
        raise LinkedInPublishError('LinkedIn access token is missing. Reconnect LinkedIn.')
    if connection.token_expires_at and connection.token_expires_at <= datetime.utcnow():
        raise LinkedInPublishError('LinkedIn access token expired. Reconnect LinkedIn.')
    return connection.access_token


def _owner_urn(connection, target='page'):
    if not connection.external_account_id:
        raise LinkedInPublishError('LinkedIn publishing identity is missing. Reconnect LinkedIn.')
    if _normalize_target(target) == 'personal':
        return f'urn:li:person:{connection.external_account_id}'
    return f'urn:li:organization:{connection.external_account_id}'


def _register_video_upload(token, owner_urn):
    response = requests.post(
        f'{LINKEDIN_ASSETS_URL}?action=registerUpload',
        headers=_rest_headers(token),
        json={
            'registerUploadRequest': {
                'recipes': ['urn:li:digitalmediaRecipe:feedshare-video'],
                'owner': owner_urn,
                'serviceRelationships': [{
                    'relationshipType': 'OWNER',
                    'identifier': 'urn:li:userGeneratedContent',
                }],
            },
        },
        timeout=30,
    )
    data = _json_or_error(response, 'Could not register LinkedIn video upload')
    value = data.get('value') or {}
    asset = value.get('asset')
    mechanisms = (value.get('uploadMechanism') or {}).get(
        'com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest'
    ) or {}
    upload_url = mechanisms.get('uploadUrl')
    if not asset or not upload_url:
        raise LinkedInPublishError('LinkedIn upload registration did not include an upload URL.')
    return asset, upload_url


def _upload_video_asset(upload_url, path):
    with path.open('rb') as video_file:
        response = requests.put(
            upload_url,
            headers={'Content-Type': 'video/mp4'},
            data=video_file,
            timeout=600,
        )
    if not response.ok:
        raise LinkedInPublishError('Could not upload video to LinkedIn.')


def _create_video_post(token, author_urn, asset_urn, title, description, visibility):
    visibility = visibility if visibility in {'PUBLIC', 'CONNECTIONS'} else 'PUBLIC'
    commentary = description or title
    response = requests.post(
        LINKEDIN_UGC_POSTS_URL,
        headers=_rest_headers(token),
        json={
            'author': author_urn,
            'lifecycleState': 'PUBLISHED',
            'specificContent': {
                'com.linkedin.ugc.ShareContent': {
                    'shareCommentary': {'text': commentary},
                    'shareMediaCategory': 'VIDEO',
                    'media': [{
                        'status': 'READY',
                        'description': {'text': commentary[:200]},
                        'media': asset_urn,
                        'title': {'text': title[:200]},
                    }],
                },
            },
            'visibility': {
                'com.linkedin.ugc.MemberNetworkVisibility': visibility,
            },
        },
        timeout=30,
    )
    _json_or_error(response, 'Could not create LinkedIn post')
    return response.headers.get('X-RestLi-Id') or ''


def _rest_headers(token):
    return {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'X-Restli-Protocol-Version': '2.0.0',
    }


def _token_expiry(token_data):
    expires_in = token_data.get('expires_in')
    if not expires_in:
        return None
    return datetime.utcnow() + timedelta(seconds=max(0, int(expires_in) - 60))


def _urn_id(urn):
    if not urn or ':' not in urn:
        return ''
    return urn.rsplit(':', 1)[-1]


def _json_or_error(response, fallback_message):
    try:
        data = response.json()
    except ValueError:
        data = {}

    if response.ok:
        return data

    message = data.get('message') or data.get('error_description') or data.get('error') or fallback_message
    raise LinkedInPublishError(str(message))
