"""Telegram Bot API helpers for sending generated MP4 videos."""
import os
import re
from pathlib import Path

import requests


TELEGRAM_CAPTION_LIMIT = 1024


class TelegramConfigError(RuntimeError):
    """Raised when Telegram Bot API settings are missing."""


class TelegramPublishError(RuntimeError):
    """Raised when Telegram video sending fails."""


def _bot_token():
    return os.getenv('TELEGRAM_BOT_TOKEN', '').strip()


def telegram_config_ready():
    return bool(_bot_token())


def default_chat_ids():
    return parse_chat_ids(os.getenv('TELEGRAM_CHAT_IDS', ''))


def parse_chat_ids(value):
    chat_ids = []
    seen = set()
    for raw in re.split(r'[\s,;]+', str(value or '')):
        chat_id = raw.strip()
        if chat_id and chat_id not in seen:
            seen.add(chat_id)
            chat_ids.append(chat_id)
    return chat_ids


def _require_config():
    if not telegram_config_ready():
        raise TelegramConfigError('Set TELEGRAM_BOT_TOKEN before sending Telegram messages.')


def send_video_message(chat_id, file_path, caption):
    """Send an MP4 video to one Telegram chat."""
    _require_config()
    chat_id = str(chat_id or '').strip()
    if not chat_id:
        raise TelegramPublishError('Telegram chat ID is required.')

    path = Path(file_path)
    if not path.exists():
        raise TelegramPublishError('Generated MP4 file was not found.')
    if path.suffix.lower() != '.mp4':
        raise TelegramPublishError('Only MP4 files can be sent through Telegram.')

    with path.open('rb') as video_file:
        response = requests.post(
            _send_video_url(),
            data={
                'chat_id': chat_id,
                'caption': _caption(caption),
                'supports_streaming': 'true',
            },
            files={'video': (path.name, video_file, 'video/mp4')},
            timeout=600,
        )
    data = _json_or_error(response, f'Could not send Telegram video to {chat_id}')
    message = data.get('result') or {}
    return {
        'chat_id': chat_id,
        'message_id': message.get('message_id'),
        'response': data,
    }


def send_video_to_chats(file_path, chat_ids, caption):
    """Send an MP4 to every configured Telegram chat."""
    chats = parse_chat_ids(' '.join(chat_ids or []))
    if not chats:
        raise TelegramPublishError('Add at least one Telegram chat ID.')

    sent = []
    failed = []
    for chat_id in chats:
        try:
            sent.append(send_video_message(chat_id, file_path, caption))
        except TelegramPublishError as exc:
            failed.append({'chat_id': chat_id, 'error': str(exc)})

    if not sent:
        first_error = failed[0]['error'] if failed else 'No Telegram messages were sent.'
        raise TelegramPublishError(first_error)

    return {
        'sent': sent,
        'failed': failed,
    }


def _send_video_url():
    return f'https://api.telegram.org/bot{_bot_token()}/sendVideo'


def _caption(value):
    caption = str(value or '').strip()
    return caption[:TELEGRAM_CAPTION_LIMIT]


def _json_or_error(response, fallback_message):
    try:
        data = response.json()
    except ValueError:
        data = {}

    if not response.ok or not data.get('ok', False):
        message = data.get('description') if isinstance(data, dict) else None
        raise TelegramPublishError(message or fallback_message)
    return data
