"""Social media connection and publishing routes."""
import json
import logging
import os
import re
from urllib.parse import quote

import requests
from flask import Blueprint, jsonify, redirect, request

from app.services.company_service import current_company_id
from app.services.storage_service import resolve_generated_file
from app.services.social.facebook_service import (
    FacebookConfigError,
    FacebookPublishError,
    create_facebook_authorization_url,
    disconnect_facebook,
    exchange_facebook_code,
    facebook_config_ready,
    fetch_instagram_media_permalink,
    get_connected_instagram_account,
    get_facebook_connection,
    upload_instagram_reel,
    upload_page_video,
)
from app.services.social.app_config_service import get_social_app_value
from app.services.social.linkedin_service import (
    LinkedInConfigError,
    LinkedInPublishError,
    create_linkedin_authorization_url,
    disconnect_linkedin,
    exchange_linkedin_code,
    get_linkedin_connection,
    linkedin_config_ready,
    upload_video_post,
)
from app.models import GenerationHistory, SocialPublishHistory
from app.services.social.tiktok_service import (
    TikTokConfigError,
    TikTokPublishError,
    create_tiktok_authorization_url,
    disconnect_tiktok,
    exchange_tiktok_code,
    get_tiktok_connection,
    tiktok_config_ready,
    upload_video_draft,
)
from app.services.social.telegram_service import (
    TelegramConfigError,
    TelegramPublishError,
    default_chat_ids,
    send_video_to_chats,
    telegram_config_ready,
)
from app.services.social.whatsapp_service import (
    WhatsAppConfigError,
    WhatsAppPublishError,
    default_recipients,
    send_video_to_recipients,
    whatsapp_config_ready,
)
from wsgi import db
from app.services.social.x_service import (
    XConfigError,
    XPublishError,
    create_x_authorization_url,
    disconnect_x,
    exchange_x_code,
    get_x_connection,
    publish_video_post,
    x_config_ready,
)
from app.services.social.youtube_service import (
    YouTubeConfigError,
    YouTubePublishError,
    create_youtube_authorization_url,
    disconnect_youtube,
    exchange_youtube_code,
    get_youtube_connection,
    upload_video,
    youtube_config_ready,
)


logger = logging.getLogger(__name__)
social_bp = Blueprint('social', __name__, url_prefix='/api/social')


def _youtube_status_payload(company_id):
    connection = get_youtube_connection(company_id)
    data = connection.to_dict() if connection else {
        'provider': 'youtube',
        'company_id': company_id,
        'connected': False,
        'external_account_id': None,
        'external_account_name': None,
        'connected_at': None,
    }
    data['configured'] = youtube_config_ready()
    return data


def _facebook_status_payload(company_id):
    connection = get_facebook_connection(company_id)
    data = connection.to_dict() if connection else {
        'provider': 'facebook',
        'company_id': company_id,
        'connected': False,
        'external_account_id': None,
        'external_account_name': None,
        'connected_at': None,
    }
    data['configured'] = facebook_config_ready()
    data['publishing_target'] = 'page'
    data['personal_sharing'] = 'manual'
    return data


def _social_public_base_url():
    return (
        get_social_app_value('facebook', 'public_base_url', 'SOCIAL_PUBLIC_BASE_URL')
        or os.getenv('APP_PUBLIC_BASE_URL')
        or ''
    ).strip().rstrip('/')


def _instagram_status_payload(company_id):
    connection = get_facebook_connection(company_id)
    data = {
        'provider': 'instagram',
        'company_id': company_id,
        'configured': facebook_config_ready() and bool(_social_public_base_url()),
        'facebook_connected': bool(connection and connection.is_connected()),
        'connected': False,
        'external_account_id': None,
        'external_account_name': None,
        'connected_at': connection.connected_at.isoformat() if connection and connection.connected_at else None,
        'publishing_target': 'reels',
        'requires_public_url': True,
        'public_base_url_configured': bool(_social_public_base_url()),
    }
    if not connection or not connection.is_connected():
        return data

    try:
        account = get_connected_instagram_account(connection)
    except FacebookPublishError as exc:
        data['message'] = str(exc)
        return data

    if account:
        data.update({
            'connected': True,
            'external_account_id': account['id'],
            'external_account_name': account.get('username') or account.get('name'),
        })
    return data


def _public_mp4_url(filename):
    base_url = _social_public_base_url()
    if not base_url:
        return ''
    return f"{base_url}/api/generation/preview/{quote(filename)}"


def _validate_public_mp4_url(video_url):
    if not video_url:
        return 'Set Public base URL in Social App Keys or SOCIAL_PUBLIC_BASE_URL so Instagram can fetch the generated MP4.'

    try:
        response = requests.get(
            video_url,
            headers={
                'Range': 'bytes=0-1',
                'User-Agent': 'DailyRates-Social-Publish-Preflight/1.0',
                'ngrok-skip-browser-warning': 'true',
            },
            timeout=20,
            stream=True,
        )
        response.close()
    except requests.RequestException as exc:
        return f'Public MP4 URL is not reachable: {exc}'

    content_type = (response.headers.get('Content-Type') or '').split(';', 1)[0].strip().lower()
    if response.status_code not in (200, 206):
        server = response.headers.get('Server') or 'unknown server'
        ngrok_error = response.headers.get('ngrok-error-code')
        if ngrok_error:
            return (
                f'Public MP4 URL returned HTTP {response.status_code} from ngrok ({ngrok_error}). '
                f'Start/restart ngrok against this Flask app port and update Public base URL in Social App Keys or SOCIAL_PUBLIC_BASE_URL: {video_url}'
            )
        return (
            f'Public MP4 URL returned HTTP {response.status_code} from {server}. '
            f'Check Public base URL in Social App Keys or SOCIAL_PUBLIC_BASE_URL and make sure it points to this Flask app: {video_url}'
        )
    if content_type != 'video/mp4':
        return (
            f'Public MP4 URL returned Content-Type "{content_type or "missing"}" instead of video/mp4. '
            f'Check Public base URL in Social App Keys or SOCIAL_PUBLIC_BASE_URL and make sure Meta can download the MP4 directly: {video_url}'
        )
    return ''


def _linkedin_status_payload(company_id, target='page'):
    connection = get_linkedin_connection(company_id, target)
    data = connection.to_dict() if connection else {
        'provider': f'linkedin_{target}',
        'company_id': company_id,
        'connected': False,
        'external_account_id': None,
        'external_account_name': None,
        'connected_at': None,
    }
    data['configured'] = linkedin_config_ready()
    data['publishing_target'] = target
    return data


def _tiktok_status_payload(company_id):
    connection = get_tiktok_connection(company_id)
    data = connection.to_dict() if connection else {
        'provider': 'tiktok',
        'company_id': company_id,
        'connected': False,
        'external_account_id': None,
        'external_account_name': None,
        'connected_at': None,
    }
    data['configured'] = tiktok_config_ready()
    data['publishing_target'] = 'inbox_draft'
    data['requires_completion_in_tiktok'] = True
    return data


def _x_status_payload(company_id):
    connection = get_x_connection(company_id)
    data = connection.to_dict() if connection else {
        'provider': 'x',
        'company_id': company_id,
        'connected': False,
        'external_account_id': None,
        'external_account_name': None,
        'connected_at': None,
    }
    data['configured'] = x_config_ready()
    data['publishing_target'] = 'post'
    return data


def _whatsapp_status_payload(company_id):
    recipients = default_recipients()
    return {
        'provider': 'whatsapp',
        'company_id': company_id,
        'configured': whatsapp_config_ready(),
        'connected': whatsapp_config_ready(),
        'publishing_target': 'business_message',
        'recipient_count': len(recipients),
        'default_recipients': recipients,
    }


def _telegram_status_payload(company_id):
    chat_ids = default_chat_ids()
    return {
        'provider': 'telegram',
        'company_id': company_id,
        'configured': telegram_config_ready(),
        'connected': telegram_config_ready(),
        'publishing_target': 'chat_message',
        'chat_count': len(chat_ids),
        'default_chat_ids': chat_ids,
    }


@social_bp.route('/hashtags', methods=['POST'])
def generate_hashtags():
    """Generate social hashtags using free local AI when available."""
    data = request.get_json(silent=True) or {}
    title = (data.get('title') or '').strip()
    country = (data.get('country') or '').strip()
    shipment_by = (data.get('shipment_by') or '').strip()
    products = data.get('products') or []
    platform = (data.get('platform') or 'social').strip()
    count = _safe_hashtag_count(data.get('count'), default=18)

    base_hashtags = _base_hashtags(country, shipment_by)
    generated_count = max(0, count - len(base_hashtags))
    excluded = set(_hashtag_key(tag) for tag in base_hashtags)
    product_hashtags = _product_hashtags(products, generated_count, excluded)
    ai_count = max(0, generated_count - len(product_hashtags))
    ai_excluded = set(excluded)
    ai_excluded.update(_hashtag_key(tag) for tag in product_hashtags)

    ai_hashtags = _ollama_hashtags(title, country, shipment_by, products, platform, ai_count, ai_excluded)
    source = 'ollama'
    if not ai_hashtags:
        ai_hashtags = _fallback_hashtags(title, ai_count, ai_excluded)
        source = 'fallback'
    generated_hashtags = _dedupe_hashtags([*product_hashtags, *ai_hashtags])
    hashtags = _dedupe_hashtags([*base_hashtags, *generated_hashtags])

    return jsonify({
        'status': 'success',
        'data': {
            'hashtags': hashtags,
            'text': ' '.join(hashtags),
            'fixed_hashtags': FIXED_SOCIAL_HASHTAGS,
            'dynamic_hashtags': _dynamic_hashtags(country, shipment_by),
            'product_hashtags': product_hashtags,
            'generated_hashtags': generated_hashtags,
            'ai_hashtags': ai_hashtags,
            'source': source,
        },
    }), 200


def _safe_hashtag_count(value, default=18):
    try:
        count = int(value)
    except (TypeError, ValueError):
        count = default
    return max(5, min(count, 30))


FIXED_SOCIAL_HASHTAGS = [
    '#wholesaleprices2025',
    '#freshvegetablesdubai',
    '#import',
    '#export',
    '#alaweermarket',
    '#easternfarmsllc',
    '#dubaiimporters',
    '#bhawanajain',
    '#nitindixit',
    '#vegetablepricesdubai',
]


def _dynamic_hashtags(country, shipment_by):
    return _dedupe_hashtags([
        _to_hashtag(country),
        _to_hashtag(shipment_by),
    ])


def _base_hashtags(country, shipment_by):
    return _dedupe_hashtags([*FIXED_SOCIAL_HASHTAGS, *_dynamic_hashtags(country, shipment_by)])


def _product_hashtags(products, count, excluded=None):
    if count <= 0:
        return []

    hashtags = []
    seen = set(excluded or set())
    for product in products or []:
        normalized = _hashtag_key(product)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        hashtags.append(f'#{normalized}')
        if len(hashtags) >= count:
            break
    return hashtags


def _ollama_hashtags(title, country, shipment_by, products, platform, count, excluded=None):
    base_url = (os.getenv('OLLAMA_BASE_URL') or '').strip()
    if not base_url or count <= 0:
        return []

    model = (os.getenv('HASHTAG_OLLAMA_MODEL') or os.getenv('OLLAMA_PDF_EXTRACTION_MODEL') or 'llama3.2').strip()
    product_text = ', '.join(str(product) for product in products[:20] if product)
    excluded_text = ', '.join(sorted(excluded or []))
    prompt = (
        f"Generate exactly {count} social media marketing hashtags for a fresh fruits and vegetables "
        f"wholesale price MP4 post in Dubai.\n"
        f"Platform: {platform}\n"
        f"Country: {country}\n"
        f"Shipment by: {shipment_by}\n"
        f"Products: {product_text}\n"
        f"Title: {title}\n"
        f"Do not include these existing hashtags: {excluded_text}\n"
        "Return only a JSON array of hashtag strings. Use lowercase, no spaces, no explanations."
    )

    try:
        response = requests.post(
            f"{base_url.rstrip('/')}/api/generate",
            json={
                'model': model,
                'prompt': prompt,
                'stream': False,
                'options': {'temperature': 0.4},
            },
            timeout=20,
        )
        if not response.ok:
            return []
        content = (response.json().get('response') or '').strip()
        return _extract_hashtags(content, limit=count, excluded=excluded)
    except requests.RequestException:
        return []


def _fallback_hashtags(title, count, excluded=None):
    if count <= 0:
        return []

    seed_terms = re.findall(r"[A-Za-z][A-Za-z0-9]{2,}", title)[:20]
    hashtags = []
    seen = set(excluded or set())
    for term in seed_terms:
        normalized = _hashtag_key(term)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        hashtags.append(f'#{normalized}')
        if len(hashtags) >= count:
            break
    return hashtags


def _extract_hashtags(content, limit=18, excluded=None):
    values = []
    try:
        parsed = json.loads(content)
        if isinstance(parsed, list):
            values = parsed
        elif isinstance(parsed, dict):
            values = parsed.get('hashtags') or []
    except ValueError:
        values = re.findall(r'#[A-Za-z0-9_]+', content)

    hashtags = []
    seen = set(excluded or set())
    for value in values:
        normalized = _hashtag_key(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        hashtags.append(f'#{normalized}')
        if len(hashtags) >= limit:
            break
    return hashtags


def _to_hashtag(value):
    normalized = _hashtag_key(value)
    return f'#{normalized}' if normalized else ''


def _hashtag_key(value):
    return re.sub(r'[^a-z0-9]+', '', str(value or '').lower())


def _dedupe_hashtags(hashtags):
    output = []
    seen = set()
    for hashtag in hashtags:
        normalized = _hashtag_key(hashtag)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        output.append(f'#{normalized}')
    return output


@social_bp.route('/youtube/status', methods=['GET'])
def youtube_status():
    """Return current company's YouTube connection status."""
    return jsonify({
        'status': 'success',
        'data': _youtube_status_payload(current_company_id()),
    }), 200


@social_bp.route('/youtube/connect-url', methods=['GET'])
def youtube_connect_url():
    """Create a Google OAuth URL for YouTube upload access."""
    try:
        auth_url = create_youtube_authorization_url(current_company_id())
        return jsonify({
            'status': 'success',
            'data': {'auth_url': auth_url},
        }), 200
    except YouTubeConfigError as exc:
        return jsonify({
            'status': 'error',
            'message': str(exc),
        }), 400
    except Exception as exc:
        logger.error("Error creating YouTube connect URL: %s", exc)
        return jsonify({
            'status': 'error',
            'message': f'Error creating YouTube connect URL: {exc}',
        }), 500


@social_bp.route('/youtube/callback', methods=['GET'])
def youtube_callback():
    """Google OAuth callback for YouTube connection."""
    if request.args.get('error'):
        return redirect('/company?youtube=error')

    code = request.args.get('code')
    state = request.args.get('state')
    if not code or not state:
        return redirect('/company?youtube=missing')

    try:
        exchange_youtube_code(code, state)
        return redirect('/company?youtube=connected')
    except Exception as exc:
        logger.error("Error connecting YouTube: %s", exc)
        return redirect('/company?youtube=error')


@social_bp.route('/youtube/disconnect', methods=['POST'])
def youtube_disconnect():
    """Disconnect YouTube from the current company."""
    disconnect_youtube(current_company_id())
    return jsonify({
        'status': 'success',
        'message': 'YouTube disconnected',
        'data': _youtube_status_payload(current_company_id()),
    }), 200


@social_bp.route('/youtube/publish', methods=['POST'])
def youtube_publish():
    """Publish a generated MP4 to the connected YouTube channel."""
    company_id = current_company_id()
    data = request.get_json(silent=True) or {}
    filename = (data.get('filename') or '').strip()
    title = (data.get('title') or '').strip()
    description = (data.get('description') or '').strip()
    privacy_status = (data.get('privacy_status') or 'private').strip().lower()

    if not filename or '/' in filename or '\\' in filename or filename.startswith('.'):
        return jsonify({
            'status': 'error',
            'message': 'Invalid generated MP4 filename',
        }), 400
    if not title:
        return jsonify({
            'status': 'error',
            'message': 'YouTube title is required',
        }), 400

    generation = GenerationHistory.query.filter_by(filename=filename, company_id=company_id).first()
    if not generation:
        return jsonify({
            'status': 'error',
            'message': 'Generated MP4 was not found for this company',
        }), 404

    filepath = resolve_generated_file(generation.file_path or filename)
    if not filepath:
        return jsonify({
            'status': 'error',
            'message': 'Generated MP4 file was not found',
        }), 404
    connection = get_youtube_connection(company_id)
    publish = SocialPublishHistory(
        company_id=company_id,
        provider='youtube',
        generation_id=generation.id,
        filename=filename,
        title=title,
        description=description,
        status='uploading',
    )
    db.session.add(publish)
    db.session.commit()

    try:
        result = upload_video(connection, filepath, title, description, privacy_status)
        publish.status = 'published'
        publish.external_post_id = result['video_id']
        publish.external_post_url = result['url']
        db.session.commit()
        return jsonify({
            'status': 'success',
            'message': 'Published to YouTube',
            'data': publish.to_dict(),
        }), 200
    except (YouTubeConfigError, YouTubePublishError) as exc:
        publish.status = 'failed'
        publish.error_message = str(exc)
        db.session.commit()
        return jsonify({
            'status': 'error',
            'message': str(exc),
            'data': publish.to_dict(),
        }), 400
    except Exception as exc:
        db.session.rollback()
        logger.error("Error publishing to YouTube: %s", exc)
        return jsonify({
            'status': 'error',
            'message': f'Error publishing to YouTube: {exc}',
        }), 500


@social_bp.route('/facebook/status', methods=['GET'])
def facebook_status():
    """Return current company's Facebook Page connection status."""
    return jsonify({
        'status': 'success',
        'data': _facebook_status_payload(current_company_id()),
    }), 200


@social_bp.route('/facebook/connect-url', methods=['GET'])
def facebook_connect_url():
    """Create a Facebook OAuth URL for Page publishing access."""
    try:
        auth_url = create_facebook_authorization_url(current_company_id())
        return jsonify({
            'status': 'success',
            'data': {'auth_url': auth_url},
        }), 200
    except FacebookConfigError as exc:
        return jsonify({
            'status': 'error',
            'message': str(exc),
        }), 400
    except Exception as exc:
        logger.error("Error creating Facebook connect URL: %s", exc)
        return jsonify({
            'status': 'error',
            'message': f'Error creating Facebook connect URL: {exc}',
        }), 500


@social_bp.route('/facebook/callback', methods=['GET'])
def facebook_callback():
    """Facebook OAuth callback for Page connection."""
    if request.args.get('error'):
        return redirect('/company?facebook=error')

    code = request.args.get('code')
    state = request.args.get('state')
    if not code or not state:
        return redirect('/company?facebook=missing')

    try:
        exchange_facebook_code(code, state)
        return redirect('/company?facebook=connected')
    except Exception as exc:
        logger.error("Error connecting Facebook: %s", exc)
        return redirect('/company?facebook=error')


@social_bp.route('/facebook/disconnect', methods=['POST'])
def facebook_disconnect():
    """Disconnect Facebook from the current company."""
    disconnect_facebook(current_company_id())
    return jsonify({
        'status': 'success',
        'message': 'Facebook disconnected',
        'data': _facebook_status_payload(current_company_id()),
    }), 200


@social_bp.route('/facebook/publish', methods=['POST'])
def facebook_publish():
    """Publish a generated MP4 to the connected Facebook Page."""
    company_id = current_company_id()
    data = request.get_json(silent=True) or {}
    filename = (data.get('filename') or '').strip()
    title = (data.get('title') or '').strip()
    description = (data.get('description') or '').strip()

    if not filename or '/' in filename or '\\' in filename or filename.startswith('.'):
        return jsonify({
            'status': 'error',
            'message': 'Invalid generated MP4 filename',
        }), 400
    if not title:
        return jsonify({
            'status': 'error',
            'message': 'Facebook title is required',
        }), 400

    generation = GenerationHistory.query.filter_by(filename=filename, company_id=company_id).first()
    if not generation:
        return jsonify({
            'status': 'error',
            'message': 'Generated MP4 was not found for this company',
        }), 404

    filepath = resolve_generated_file(generation.file_path or filename)
    if not filepath:
        return jsonify({
            'status': 'error',
            'message': 'Generated MP4 file was not found',
        }), 404
    connection = get_facebook_connection(company_id)
    publish = SocialPublishHistory(
        company_id=company_id,
        provider='facebook',
        generation_id=generation.id,
        filename=filename,
        title=title,
        description=description,
        status='uploading',
    )
    db.session.add(publish)
    db.session.commit()

    try:
        result = upload_page_video(connection, filepath, title, description)
        publish.status = 'published'
        publish.external_post_id = result['video_id']
        publish.external_post_url = result['url']
        db.session.commit()
        return jsonify({
            'status': 'success',
            'message': 'Published to Facebook Page',
            'data': publish.to_dict(),
        }), 200
    except (FacebookConfigError, FacebookPublishError) as exc:
        publish.status = 'failed'
        publish.error_message = str(exc)
        db.session.commit()
        return jsonify({
            'status': 'error',
            'message': str(exc),
            'data': publish.to_dict(),
        }), 400
    except Exception as exc:
        db.session.rollback()
        logger.error("Error publishing to Facebook: %s", exc)
        return jsonify({
            'status': 'error',
            'message': f'Error publishing to Facebook: {exc}',
        }), 500


@social_bp.route('/instagram/status', methods=['GET'])
def instagram_status():
    """Return current company's Instagram publishing status."""
    return jsonify({
        'status': 'success',
        'data': _instagram_status_payload(current_company_id()),
    }), 200


@social_bp.route('/instagram/publish', methods=['POST'])
def instagram_publish():
    """Publish a generated MP4 to the linked Instagram professional account."""
    company_id = current_company_id()
    data = request.get_json(silent=True) or {}
    filename = (data.get('filename') or '').strip()
    title = (data.get('title') or '').strip()
    description = (data.get('description') or '').strip()

    if not filename or '/' in filename or '\\' in filename or filename.startswith('.'):
        return jsonify({
            'status': 'error',
            'message': 'Invalid generated MP4 filename',
        }), 400
    if not title:
        return jsonify({
            'status': 'error',
            'message': 'Instagram title is required',
        }), 400

    generation = GenerationHistory.query.filter_by(filename=filename, company_id=company_id).first()
    if not generation:
        return jsonify({
            'status': 'error',
            'message': 'Generated MP4 was not found for this company',
        }), 404

    connection = get_facebook_connection(company_id)
    existing_publish = SocialPublishHistory.query.filter_by(
        company_id=company_id,
        provider='instagram',
        generation_id=generation.id,
        status='published',
    ).order_by(SocialPublishHistory.created_at.desc()).first()
    if existing_publish:
        if connection and connection.is_connected() and existing_publish.external_post_id:
            permalink = fetch_instagram_media_permalink(connection, existing_publish.external_post_id)
            if permalink and permalink != existing_publish.external_post_url:
                existing_publish.external_post_url = permalink
                db.session.commit()
        return jsonify({
            'status': 'success',
            'message': 'Already published to Instagram',
            'data': existing_publish.to_dict(),
        }), 200

    video_url = _public_mp4_url(filename)
    public_url_error = _validate_public_mp4_url(video_url)
    if public_url_error:
        return jsonify({
            'status': 'error',
            'message': public_url_error,
        }), 400

    caption = '\n\n'.join(part for part in [title, description] if part)
    publish = SocialPublishHistory(
        company_id=company_id,
        provider='instagram',
        generation_id=generation.id,
        filename=filename,
        title=title,
        description=description,
        status='uploading',
    )
    db.session.add(publish)
    db.session.commit()

    try:
        result = upload_instagram_reel(connection, video_url, caption)
        publish.status = 'published'
        publish.external_post_id = result['media_id']
        publish.external_post_url = result['url']
        db.session.commit()
        return jsonify({
            'status': 'success',
            'message': 'Published to Instagram',
            'data': publish.to_dict(),
        }), 200
    except (FacebookConfigError, FacebookPublishError) as exc:
        publish.status = 'failed'
        publish.error_message = str(exc)
        db.session.commit()
        return jsonify({
            'status': 'error',
            'message': str(exc),
            'data': publish.to_dict(),
        }), 400
    except Exception as exc:
        db.session.rollback()
        logger.error("Error publishing to Instagram: %s", exc)
        return jsonify({
            'status': 'error',
            'message': f'Error publishing to Instagram: {exc}',
        }), 500


@social_bp.route('/tiktok/status', methods=['GET'])
def tiktok_status():
    """Return current company's TikTok connection status."""
    return jsonify({
        'status': 'success',
        'data': _tiktok_status_payload(current_company_id()),
    }), 200


@social_bp.route('/tiktok/connect-url', methods=['GET'])
def tiktok_connect_url():
    """Create a TikTok OAuth URL for draft video upload access."""
    try:
        auth_url = create_tiktok_authorization_url(current_company_id())
        return jsonify({
            'status': 'success',
            'data': {'auth_url': auth_url},
        }), 200
    except TikTokConfigError as exc:
        return jsonify({
            'status': 'error',
            'message': str(exc),
        }), 400
    except Exception as exc:
        logger.error("Error creating TikTok connect URL: %s", exc)
        return jsonify({
            'status': 'error',
            'message': f'Error creating TikTok connect URL: {exc}',
        }), 500


@social_bp.route('/tiktok/callback', methods=['GET'])
def tiktok_callback():
    """TikTok OAuth callback for account connection."""
    if request.args.get('error'):
        return redirect('/company?tiktok=error')

    code = request.args.get('code')
    state = request.args.get('state')
    if not code or not state:
        return redirect('/company?tiktok=missing')

    try:
        exchange_tiktok_code(code, state)
        return redirect('/company?tiktok=connected')
    except Exception as exc:
        logger.error("Error connecting TikTok: %s", exc)
        return redirect('/company?tiktok=error')


@social_bp.route('/tiktok/disconnect', methods=['POST'])
def tiktok_disconnect():
    """Disconnect TikTok from the current company."""
    disconnect_tiktok(current_company_id())
    return jsonify({
        'status': 'success',
        'message': 'TikTok disconnected',
        'data': _tiktok_status_payload(current_company_id()),
    }), 200


@social_bp.route('/tiktok/publish', methods=['POST'])
def tiktok_publish():
    """Upload a generated MP4 draft to the connected TikTok account."""
    company_id = current_company_id()
    data = request.get_json(silent=True) or {}
    filename = (data.get('filename') or '').strip()
    title = (data.get('title') or '').strip()
    description = (data.get('description') or '').strip()

    if not filename or '/' in filename or '\\' in filename or filename.startswith('.'):
        return jsonify({
            'status': 'error',
            'message': 'Invalid generated MP4 filename',
        }), 400
    if not title:
        return jsonify({
            'status': 'error',
            'message': 'TikTok title is required',
        }), 400

    generation = GenerationHistory.query.filter_by(filename=filename, company_id=company_id).first()
    if not generation:
        return jsonify({
            'status': 'error',
            'message': 'Generated MP4 was not found for this company',
        }), 404

    filepath = resolve_generated_file(generation.file_path or filename)
    if not filepath:
        return jsonify({
            'status': 'error',
            'message': 'Generated MP4 file was not found',
        }), 404
    connection = get_tiktok_connection(company_id)
    publish = SocialPublishHistory(
        company_id=company_id,
        provider='tiktok',
        generation_id=generation.id,
        filename=filename,
        title=title,
        description=description,
        status='uploading',
    )
    db.session.add(publish)
    db.session.commit()

    try:
        result = upload_video_draft(connection, filepath)
        publish.status = 'uploaded'
        publish.external_post_id = result['publish_id']
        publish.external_post_url = result.get('url') or None
        db.session.commit()
        return jsonify({
            'status': 'success',
            'message': 'Uploaded to TikTok. Open TikTok inbox to finish posting.',
            'data': publish.to_dict(),
        }), 200
    except (TikTokConfigError, TikTokPublishError) as exc:
        publish.status = 'failed'
        publish.error_message = str(exc)
        db.session.commit()
        return jsonify({
            'status': 'error',
            'message': str(exc),
            'data': publish.to_dict(),
        }), 400
    except Exception as exc:
        db.session.rollback()
        logger.error("Error uploading to TikTok: %s", exc)
        return jsonify({
            'status': 'error',
            'message': f'Error uploading to TikTok: {exc}',
        }), 500


@social_bp.route('/x/status', methods=['GET'])
def x_status():
    """Return current company's X connection status."""
    return jsonify({
        'status': 'success',
        'data': _x_status_payload(current_company_id()),
    }), 200


@social_bp.route('/x/connect-url', methods=['GET'])
def x_connect_url():
    """Create an X OAuth URL for Post publishing access."""
    try:
        auth_url = create_x_authorization_url(current_company_id())
        return jsonify({
            'status': 'success',
            'data': {'auth_url': auth_url},
        }), 200
    except XConfigError as exc:
        return jsonify({
            'status': 'error',
            'message': str(exc),
        }), 400
    except Exception as exc:
        logger.error("Error creating X connect URL: %s", exc)
        return jsonify({
            'status': 'error',
            'message': f'Error creating X connect URL: {exc}',
        }), 500


@social_bp.route('/x/callback', methods=['GET'])
def x_callback():
    """X OAuth callback for account connection."""
    if request.args.get('error'):
        return redirect('/company?x=error')

    code = request.args.get('code')
    state = request.args.get('state')
    if not code or not state:
        return redirect('/company?x=missing')

    try:
        exchange_x_code(code, state)
        return redirect('/company?x=connected')
    except Exception as exc:
        logger.error("Error connecting X: %s", exc)
        return redirect('/company?x=error')


@social_bp.route('/x/disconnect', methods=['POST'])
def x_disconnect():
    """Disconnect X from the current company."""
    disconnect_x(current_company_id())
    return jsonify({
        'status': 'success',
        'message': 'X disconnected',
        'data': _x_status_payload(current_company_id()),
    }), 200


@social_bp.route('/x/publish', methods=['POST'])
def x_publish():
    """Publish a generated MP4 Post to the connected X account."""
    company_id = current_company_id()
    data = request.get_json(silent=True) or {}
    filename = (data.get('filename') or '').strip()
    title = (data.get('title') or '').strip()
    description = (data.get('description') or '').strip()

    if not filename or '/' in filename or '\\' in filename or filename.startswith('.'):
        return jsonify({
            'status': 'error',
            'message': 'Invalid generated MP4 filename',
        }), 400
    if not title:
        return jsonify({
            'status': 'error',
            'message': 'X Post title is required',
        }), 400

    generation = GenerationHistory.query.filter_by(filename=filename, company_id=company_id).first()
    if not generation:
        return jsonify({
            'status': 'error',
            'message': 'Generated MP4 was not found for this company',
        }), 404

    filepath = resolve_generated_file(generation.file_path or filename)
    if not filepath:
        return jsonify({
            'status': 'error',
            'message': 'Generated MP4 file was not found',
        }), 404
    connection = get_x_connection(company_id)
    post_text = '\n\n'.join(part for part in [title, description] if part).strip()
    publish = SocialPublishHistory(
        company_id=company_id,
        provider='x',
        generation_id=generation.id,
        filename=filename,
        title=title,
        description=description,
        status='uploading',
    )
    db.session.add(publish)
    db.session.commit()

    try:
        result = publish_video_post(connection, filepath, post_text)
        publish.status = 'published'
        publish.external_post_id = result['post_id']
        publish.external_post_url = result['url']
        db.session.commit()
        return jsonify({
            'status': 'success',
            'message': 'Published to X',
            'data': publish.to_dict(),
        }), 200
    except (XConfigError, XPublishError) as exc:
        publish.status = 'failed'
        publish.error_message = str(exc)
        db.session.commit()
        return jsonify({
            'status': 'error',
            'message': str(exc),
            'data': publish.to_dict(),
        }), 400
    except Exception as exc:
        db.session.rollback()
        logger.error("Error publishing to X: %s", exc)
        return jsonify({
            'status': 'error',
            'message': f'Error publishing to X: {exc}',
        }), 500


@social_bp.route('/whatsapp/status', methods=['GET'])
def whatsapp_status():
    """Return current company's WhatsApp Cloud API configuration status."""
    return jsonify({
        'status': 'success',
        'data': _whatsapp_status_payload(current_company_id()),
    }), 200


@social_bp.route('/whatsapp/publish', methods=['POST'])
def whatsapp_publish():
    """Send a generated MP4 through WhatsApp Cloud API."""
    company_id = current_company_id()
    data = request.get_json(silent=True) or {}
    filename = (data.get('filename') or '').strip()
    title = (data.get('title') or '').strip()
    description = (data.get('description') or '').strip()
    recipients = data.get('recipients') or []

    if isinstance(recipients, str):
        recipients = re.split(r'[\s,;]+', recipients)

    if not filename or '/' in filename or '\\' in filename or filename.startswith('.'):
        return jsonify({
            'status': 'error',
            'message': 'Invalid generated MP4 filename',
        }), 400
    if not title:
        return jsonify({
            'status': 'error',
            'message': 'WhatsApp caption title is required',
        }), 400

    generation = GenerationHistory.query.filter_by(filename=filename, company_id=company_id).first()
    if not generation:
        return jsonify({
            'status': 'error',
            'message': 'Generated MP4 was not found for this company',
        }), 404

    filepath = resolve_generated_file(generation.file_path or filename)
    if not filepath:
        return jsonify({
            'status': 'error',
            'message': 'Generated MP4 file was not found',
        }), 404
    caption = '\n\n'.join(part for part in [title, description] if part).strip()
    publish = SocialPublishHistory(
        company_id=company_id,
        provider='whatsapp',
        generation_id=generation.id,
        filename=filename,
        title=title,
        description=description,
        status='sending',
    )
    db.session.add(publish)
    db.session.commit()

    try:
        result = send_video_to_recipients(filepath, recipients or default_recipients(), caption)
        message_ids = [item.get('message_id') for item in result['sent'] if item.get('message_id')]
        publish.status = 'published' if not result['failed'] else 'partial'
        publish.external_post_id = ','.join(message_ids)[:255] if message_ids else result['media_id']
        if result['failed']:
            publish.error_message = json.dumps(result['failed'])[:1000]
        db.session.commit()
        return jsonify({
            'status': 'success',
            'message': f"Sent WhatsApp video to {len(result['sent'])} recipient(s)",
            'data': {
                **publish.to_dict(),
                'sent': result['sent'],
                'failed': result['failed'],
            },
        }), 200
    except (WhatsAppConfigError, WhatsAppPublishError) as exc:
        publish.status = 'failed'
        publish.error_message = str(exc)
        db.session.commit()
        return jsonify({
            'status': 'error',
            'message': str(exc),
            'data': publish.to_dict(),
        }), 400
    except Exception as exc:
        db.session.rollback()
        logger.error("Error sending WhatsApp video: %s", exc)
        return jsonify({
            'status': 'error',
            'message': f'Error sending WhatsApp video: {exc}',
        }), 500


@social_bp.route('/telegram/status', methods=['GET'])
def telegram_status():
    """Return current company's Telegram Bot API configuration status."""
    return jsonify({
        'status': 'success',
        'data': _telegram_status_payload(current_company_id()),
    }), 200


@social_bp.route('/telegram/publish', methods=['POST'])
def telegram_publish():
    """Send a generated MP4 through Telegram Bot API."""
    company_id = current_company_id()
    data = request.get_json(silent=True) or {}
    filename = (data.get('filename') or '').strip()
    title = (data.get('title') or '').strip()
    description = (data.get('description') or '').strip()
    chat_ids = data.get('chat_ids') or []

    if isinstance(chat_ids, str):
        chat_ids = re.split(r'[\s,;]+', chat_ids)

    if not filename or '/' in filename or '\\' in filename or filename.startswith('.'):
        return jsonify({
            'status': 'error',
            'message': 'Invalid generated MP4 filename',
        }), 400
    if not title:
        return jsonify({
            'status': 'error',
            'message': 'Telegram caption title is required',
        }), 400

    generation = GenerationHistory.query.filter_by(filename=filename, company_id=company_id).first()
    if not generation:
        return jsonify({
            'status': 'error',
            'message': 'Generated MP4 was not found for this company',
        }), 404

    filepath = resolve_generated_file(generation.file_path or filename)
    if not filepath:
        return jsonify({
            'status': 'error',
            'message': 'Generated MP4 file was not found',
        }), 404
    caption = '\n\n'.join(part for part in [title, description] if part).strip()
    publish = SocialPublishHistory(
        company_id=company_id,
        provider='telegram',
        generation_id=generation.id,
        filename=filename,
        title=title,
        description=description,
        status='sending',
    )
    db.session.add(publish)
    db.session.commit()

    try:
        result = send_video_to_chats(filepath, chat_ids or default_chat_ids(), caption)
        message_ids = [str(item.get('message_id')) for item in result['sent'] if item.get('message_id')]
        publish.status = 'published' if not result['failed'] else 'partial'
        publish.external_post_id = ','.join(message_ids)[:255] if message_ids else None
        if result['failed']:
            publish.error_message = json.dumps(result['failed'])[:1000]
        db.session.commit()
        return jsonify({
            'status': 'success',
            'message': f"Sent Telegram video to {len(result['sent'])} chat(s)",
            'data': {
                **publish.to_dict(),
                'sent': result['sent'],
                'failed': result['failed'],
            },
        }), 200
    except (TelegramConfigError, TelegramPublishError) as exc:
        publish.status = 'failed'
        publish.error_message = str(exc)
        db.session.commit()
        return jsonify({
            'status': 'error',
            'message': str(exc),
            'data': publish.to_dict(),
        }), 400
    except Exception as exc:
        db.session.rollback()
        logger.error("Error sending Telegram video: %s", exc)
        return jsonify({
            'status': 'error',
            'message': f'Error sending Telegram video: {exc}',
        }), 500


@social_bp.route('/linkedin/status', methods=['GET'])
def linkedin_status():
    """Return current company's LinkedIn Page connection status."""
    return _linkedin_status_response('page')


@social_bp.route('/linkedin/<target>/status', methods=['GET'])
def linkedin_target_status(target):
    """Return current company's selected LinkedIn connection status."""
    return _linkedin_status_response(target)


def _linkedin_status_response(target):
    try:
        return jsonify({
            'status': 'success',
            'data': _linkedin_status_payload(current_company_id(), target),
        }), 200
    except LinkedInPublishError as exc:
        return jsonify({
            'status': 'error',
            'message': str(exc),
        }), 400


@social_bp.route('/linkedin/connect-url', methods=['GET'])
def linkedin_connect_url():
    """Create a LinkedIn OAuth URL for Page publishing access."""
    return _linkedin_connect_url_response('page')


@social_bp.route('/linkedin/<target>/connect-url', methods=['GET'])
def linkedin_target_connect_url(target):
    """Create a LinkedIn OAuth URL for the selected publishing target."""
    return _linkedin_connect_url_response(target)


def _linkedin_connect_url_response(target):
    try:
        auth_url = create_linkedin_authorization_url(current_company_id(), target)
        return jsonify({
            'status': 'success',
            'data': {'auth_url': auth_url},
        }), 200
    except (LinkedInConfigError, LinkedInPublishError) as exc:
        return jsonify({
            'status': 'error',
            'message': str(exc),
        }), 400
    except Exception as exc:
        logger.error("Error creating LinkedIn connect URL: %s", exc)
        return jsonify({
            'status': 'error',
            'message': f'Error creating LinkedIn connect URL: {exc}',
        }), 500


@social_bp.route('/linkedin/callback', methods=['GET'])
def linkedin_callback():
    """LinkedIn OAuth callback for member connection."""
    if request.args.get('error'):
        return redirect('/company?linkedin=error')

    code = request.args.get('code')
    state = request.args.get('state')
    if not code or not state:
        return redirect('/company?linkedin=missing')

    try:
        exchange_linkedin_code(code, state)
        return redirect('/company?linkedin=connected')
    except Exception as exc:
        logger.error("Error connecting LinkedIn: %s", exc)
        return redirect('/company?linkedin=error')


@social_bp.route('/linkedin/disconnect', methods=['POST'])
def linkedin_disconnect():
    """Disconnect LinkedIn Page from the current company."""
    return _linkedin_disconnect_response('page')


@social_bp.route('/linkedin/<target>/disconnect', methods=['POST'])
def linkedin_target_disconnect(target):
    """Disconnect the selected LinkedIn target from the current company."""
    return _linkedin_disconnect_response(target)


def _linkedin_disconnect_response(target):
    disconnect_linkedin(current_company_id(), target)
    return jsonify({
        'status': 'success',
        'message': 'LinkedIn disconnected',
        'data': _linkedin_status_payload(current_company_id(), target),
    }), 200


@social_bp.route('/linkedin/publish', methods=['POST'])
def linkedin_publish():
    """Publish a generated MP4 to the connected LinkedIn Page."""
    return _linkedin_publish_response('page')


@social_bp.route('/linkedin/<target>/publish', methods=['POST'])
def linkedin_target_publish(target):
    """Publish a generated MP4 to the selected LinkedIn target."""
    return _linkedin_publish_response(target)


def _linkedin_publish_response(target):
    company_id = current_company_id()
    data = request.get_json(silent=True) or {}
    filename = (data.get('filename') or '').strip()
    title = (data.get('title') or '').strip()
    description = (data.get('description') or '').strip()
    visibility = (data.get('visibility') or 'PUBLIC').strip().upper()

    if not filename or '/' in filename or '\\' in filename or filename.startswith('.'):
        return jsonify({
            'status': 'error',
            'message': 'Invalid generated MP4 filename',
        }), 400
    if not title:
        return jsonify({
            'status': 'error',
            'message': 'LinkedIn title is required',
        }), 400

    generation = GenerationHistory.query.filter_by(filename=filename, company_id=company_id).first()
    if not generation:
        return jsonify({
            'status': 'error',
            'message': 'Generated MP4 was not found for this company',
        }), 404

    filepath = resolve_generated_file(generation.file_path or filename)
    if not filepath:
        return jsonify({
            'status': 'error',
            'message': 'Generated MP4 file was not found',
        }), 404
    connection = get_linkedin_connection(company_id, target)
    publish = SocialPublishHistory(
        company_id=company_id,
        provider=f'linkedin_{target}',
        generation_id=generation.id,
        filename=filename,
        title=title,
        description=description,
        status='uploading',
    )
    db.session.add(publish)
    db.session.commit()

    try:
        result = upload_video_post(connection, filepath, title, description, visibility, target)
        publish.status = 'published'
        publish.external_post_id = result['post_id']
        publish.external_post_url = result['url']
        db.session.commit()
        return jsonify({
            'status': 'success',
            'message': 'Published to LinkedIn',
            'data': publish.to_dict(),
        }), 200
    except (LinkedInConfigError, LinkedInPublishError) as exc:
        publish.status = 'failed'
        publish.error_message = str(exc)
        db.session.commit()
        return jsonify({
            'status': 'error',
            'message': str(exc),
            'data': publish.to_dict(),
        }), 400
    except Exception as exc:
        db.session.rollback()
        logger.error("Error publishing to LinkedIn: %s", exc)
        return jsonify({
            'status': 'error',
            'message': f'Error publishing to LinkedIn: {exc}',
        }), 500
