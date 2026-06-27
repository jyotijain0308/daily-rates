"""Cleanup utilities for generated output files."""
import logging
from datetime import date, datetime
from pathlib import Path

from src.config import (
    OUTPUT_CLEANUP_DIRS,
    OUTPUT_CLEANUP_ENABLED,
    OUTPUT_CLEANUP_EXTENSIONS,
)

logger = logging.getLogger(__name__)


def cleanup_previous_day_outputs(today: date | None = None) -> int:
    """Delete generated output files older than the current day."""
    if not OUTPUT_CLEANUP_ENABLED:
        return 0

    today = today or date.today()
    deleted_count = 0

    for output_dir in OUTPUT_CLEANUP_DIRS:
        directory = Path(output_dir)
        if not directory.exists():
            continue

        for file_path in directory.iterdir():
            if not file_path.is_file():
                continue

            if file_path.suffix.lower() not in OUTPUT_CLEANUP_EXTENSIONS:
                continue

            modified_day = datetime.fromtimestamp(file_path.stat().st_mtime).date()
            if modified_day >= today:
                continue

            try:
                file_path.unlink()
                deleted_count += 1
            except OSError as exc:
                logger.warning("Could not delete old output file %s: %s", file_path, exc)

    if deleted_count:
        logger.info("Cleaned up %s old output file(s)", deleted_count)

    return deleted_count
