"""WhatsApp Cloud API helpers for sending generated MP4 videos."""
import os
import re
from pathlib import Path

import requests


WHATSAPP_DEFAULT_GRAPH_VERSION = 'v23.0'
WHATSAPP_CAPTION_LIMIT = 1024


class WhatsAppConfigError(RuntimeError):
    """Raised when WhatsApp Cloud API settings are missing."""


class WhatsAppPublishError(RuntimeError):
    """Raised when WhatsApp media upload or message send fails."""


def _access_token():
    return os.getenv('WHATSAPP_ACCESS_TOKEN', '').strip()


def _phone_number_id():
    return os.getenv('WHATSAPP_PHONE_NUMBER_ID', '').strip()


def _graph_version():
    return (
        os.getenv('WHATSAPP_GRAPH_VERSION')
        or os.getenv('FACEBOOK_GRAPH_VERSION')
        or WHATSAPP_DEFAULT_GRAPH_VERSION
    ).strip()


def whatsapp_config_ready():
    return bool(_access_token() and _phone_number_id())


def default_recipients():
    return parse_recipients(os.getenv('WHATSAPP_RECIPIENTS', ''))


def parse_recipients(value):
    recipients = []
    seen = set()
    for raw in re.split(r'[\s,;]+', str(value or '')):
        phone = normalize_phone_number(raw)
        if phone and phone not in seen:
            seen.add(phone)
            recipients.append(phone)
    return recipients


def normalize_phone_number(value):
    phone = re.sub(r'[^\d+]', '', str(value or '').strip())
    if phone.startswith('+'):
        phone = phone[1:]
    if not phone or not phone.isdigit():
        return ''
    return phone


def _require_config():
    if not whatsapp_config_ready():
        raise WhatsAppConfigError(
            'Set WHATSAPP_ACCESS_TOKEN and WHATSAPP_PHONE_NUMBER_ID before sending WhatsApp messages.'
        )


def upload_video(file_path):
    """Upload an MP4 to WhatsApp Cloud API media storage and return the media id."""
    _require_config()
    path = Path(file_path)
    if not path.exists():
        raise WhatsAppPublishError('Generated MP4 file was not found.')
    if path.suffix.lower() != '.mp4':
        raise WhatsAppPublishError('Only MP4 files can be sent through WhatsApp.')

    with path.open('rb') as video_file:
        response = requests.post(
            _media_url(),
            headers={'Authorization': f'Bearer {_access_token()}'},
            data={'messaging_product': 'whatsapp'},
            files={'file': (path.name, video_file, 'video/mp4')},
            timeout=600,
        )
    data = _json_or_error(response, 'Could not upload video to WhatsApp')
    media_id = data.get('id')
    if not media_id:
        raise WhatsAppPublishError('WhatsApp media upload did not return a media id.')
    return media_id


def send_video_message(recipient, media_id, caption):
    """Send a previously uploaded WhatsApp video media object to one recipient."""
    _require_config()
    phone = normalize_phone_number(recipient)
    if not phone:
        raise WhatsAppPublishError('WhatsApp recipient phone number is invalid.')

    response = requests.post(
        _messages_url(),
        headers={
            'Authorization': f'Bearer {_access_token()}',
            'Content-Type': 'application/json; charset=UTF-8',
        },
        json={
            'messaging_product': 'whatsapp',
            'recipient_type': 'individual',
            'to': phone,
            'type': 'video',
            'video': {
                'id': media_id,
                'caption': _caption(caption),
            },
        },
        timeout=30,
    )
    data = _json_or_error(response, f'Could not send WhatsApp video to {phone}')
    messages = data.get('messages') or []
    message_id = messages[0].get('id') if messages else None
    return {
        'recipient': phone,
        'message_id': message_id,
        'response': data,
    }


def send_video_to_recipients(file_path, recipients, caption):
    """Upload an MP4 once and send it to every recipient."""
    phones = parse_recipients(' '.join(recipients or []))
    if not phones:
        raise WhatsAppPublishError('Add at least one WhatsApp recipient phone number.')

    media_id = upload_video(file_path)
    sent = []
    failed = []
    for phone in phones:
        try:
            sent.append(send_video_message(phone, media_id, caption))
        except WhatsAppPublishError as exc:
            failed.append({'recipient': phone, 'error': str(exc)})

    if not sent:
        first_error = failed[0]['error'] if failed else 'No WhatsApp messages were sent.'
        raise WhatsAppPublishError(first_error)

    return {
        'media_id': media_id,
        'sent': sent,
        'failed': failed,
    }


def _media_url():
    return f'https://graph.facebook.com/{_graph_version()}/{_phone_number_id()}/media'


def _messages_url():
    return f'https://graph.facebook.com/{_graph_version()}/{_phone_number_id()}/messages'


def _caption(value):
    caption = str(value or '').strip()
    return caption[:WHATSAPP_CAPTION_LIMIT]


def _json_or_error(response, fallback_message):
    try:
        data = response.json()
    except ValueError:
        data = {}

    if not response.ok:
        error = data.get('error') if isinstance(data, dict) else None
        message = (
            (error or {}).get('message')
            or data.get('message')
            or fallback_message
        )
        raise WhatsAppPublishError(message)
    return data
