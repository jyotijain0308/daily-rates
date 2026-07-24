"""Database-backed social app configuration helpers."""
import os

from flask import has_app_context

from app.models import SystemConfiguration
from wsgi import db


CONFIG_KEY_PREFIX = 'social_app_config.'

PROVIDER_FIELDS = {
    'youtube': {
        'client_id': 'YOUTUBE_CLIENT_ID',
        'client_secret': 'YOUTUBE_CLIENT_SECRET',
        'redirect_uri': 'YOUTUBE_REDIRECT_URI',
    },
    'facebook': {
        'app_id': 'FACEBOOK_APP_ID',
        'app_secret': 'FACEBOOK_APP_SECRET',
        'redirect_uri': 'FACEBOOK_REDIRECT_URI',
        'graph_version': 'FACEBOOK_GRAPH_VERSION',
        'login_config_id': 'FACEBOOK_LOGIN_CONFIG_ID',
        'scopes': 'FACEBOOK_SCOPES',
        'public_base_url': 'SOCIAL_PUBLIC_BASE_URL',
    },
    'x': {
        'client_id': 'X_CLIENT_ID',
        'client_secret': 'X_CLIENT_SECRET',
        'redirect_uri': 'X_REDIRECT_URI',
        'scopes': 'X_SCOPES',
        'media_category': 'X_MEDIA_CATEGORY',
    },
    'linkedin': {
        'client_id': 'LINKEDIN_CLIENT_ID',
        'client_secret': 'LINKEDIN_CLIENT_SECRET',
        'redirect_uri': 'LINKEDIN_REDIRECT_URI',
        'personal_scopes': 'LINKEDIN_PERSONAL_SCOPES',
        'page_scopes': 'LINKEDIN_PAGE_SCOPES',
        'prompt': 'LINKEDIN_PROMPT',
    },
}


SECRET_FIELDS = {
    'client_secret',
    'app_secret',
    'access_token',
    'bot_token',
}


def _config_key(provider):
    return f'{CONFIG_KEY_PREFIX}{provider}'


def get_social_app_config(provider):
    return SystemConfiguration.query.filter_by(key=_config_key(provider)).first()


def get_social_app_settings(provider):
    if not has_app_context():
        return {}
    config = get_social_app_config(provider)
    return config.value if config else {}


def get_social_app_value(provider, key, env_key=None, default=''):
    settings = get_social_app_settings(provider)
    value = (settings.get(key) or '').strip()
    if value:
        return value
    return (os.getenv(env_key or PROVIDER_FIELDS.get(provider, {}).get(key, ''), default) or default).strip()


def save_social_app_settings(provider, settings):
    config = get_social_app_config(provider)
    if not config:
        config = SystemConfiguration(key=_config_key(provider))
        db.session.add(config)
    config.value = settings
    db.session.commit()
    return config


def merge_social_app_settings(provider, incoming):
    allowed = PROVIDER_FIELDS.get(provider, {})
    existing = get_social_app_settings(provider)
    merged = dict(existing)

    for key in allowed:
        if key not in incoming:
            continue
        value = (incoming.get(key) or '').strip()
        if value == '********' and key in SECRET_FIELDS:
            continue
        if value:
            merged[key] = value
        else:
            merged.pop(key, None)

    return save_social_app_settings(provider, merged)


def social_app_config_to_dict(provider):
    config = get_social_app_config(provider)
    fields = PROVIDER_FIELDS.get(provider, {})
    settings = {}
    source = 'database' if config else 'environment'
    db_settings = config.value if config else {}

    for key, env_key in fields.items():
        value = (db_settings.get(key) or '').strip()
        if value:
            settings[key] = '********' if key in SECRET_FIELDS else value
            continue
        env_value = (os.getenv(env_key, '') or '').strip()
        settings[key] = '********' if key in SECRET_FIELDS and env_value else env_value

    configured = _provider_configured(provider, {
        key: get_social_app_value(provider, key, env_key)
        for key, env_key in fields.items()
    })
    return {
        'provider': provider,
        'settings': settings,
        'configured': configured,
        'source': source,
    }


def _provider_configured(provider, settings):
    if provider == 'youtube':
        return bool(settings.get('client_id') and settings.get('client_secret'))
    if provider == 'facebook':
        return bool(settings.get('app_id') and settings.get('app_secret'))
    if provider == 'x':
        return bool(settings.get('client_id'))
    if provider == 'linkedin':
        return bool(settings.get('client_id') and settings.get('client_secret'))
    return False
