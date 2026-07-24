"""System-wide configuration API routes."""
import logging

from flask import Blueprint, jsonify, request

from app.services.social.app_config_service import (
    PROVIDER_FIELDS,
    merge_social_app_settings,
    social_app_config_to_dict,
)


logger = logging.getLogger(__name__)
system_bp = Blueprint('system', __name__, url_prefix='/api/system')


@system_bp.route('/social-app-configs', methods=['GET'])
def get_social_app_configs():
    """Return system-wide social app key configuration."""
    return jsonify({
        'status': 'success',
        'data': {
            provider: social_app_config_to_dict(provider)
            for provider in PROVIDER_FIELDS
        },
    }), 200


@system_bp.route('/social-app-configs/<provider>', methods=['PUT'])
def update_social_app_config(provider):
    """Save system-wide social app keys."""
    if provider not in PROVIDER_FIELDS:
        return jsonify({
            'status': 'error',
            'message': 'Unsupported social provider',
        }), 400

    data = request.get_json(silent=True) or {}
    merge_social_app_settings(provider, data.get('settings') or data)
    return jsonify({
        'status': 'success',
        'message': 'Social app keys saved successfully',
        'data': social_app_config_to_dict(provider),
    }), 200
