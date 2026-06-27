#!/usr/bin/env python3
"""Development server entry point"""
import logging
import os
import socket
from wsgi import create_app

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)
app = create_app()


def find_available_port(start: int, max_attempts: int = 10) -> int:
    """Return the first available port starting from `start`."""
    for offset in range(max_attempts):
        port = start + offset
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(('0.0.0.0', port))
                return port
            except OSError:
                continue
    raise RuntimeError(f'No available port found in range {start}-{start + max_attempts - 1}')


if __name__ == '__main__':
    # Default to 5001 — macOS AirPlay Receiver often occupies port 5000
    requested_port = int(os.environ.get('PORT', 5001))
    debug = os.environ.get('FLASK_DEBUG', '1') == '1'

    try:
        port = find_available_port(requested_port)
    except RuntimeError as exc:
        logger.error(str(exc))
        raise SystemExit(1) from exc

    if port != requested_port:
        logger.warning(
            'Port %s is in use; starting on http://localhost:%s instead',
            requested_port, port
        )
    else:
        logger.info('Starting server at http://localhost:%s', port)

    app.run(host='0.0.0.0', port=port, debug=debug)
