"""Cleanup utilities for generated output files."""
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

from app.services.generation.config import (
    OUTPUT_CLEANUP_DIRS,
    OUTPUT_CLEANUP_ENABLED,
    OUTPUT_CLEANUP_EXTENSIONS,
)
from app.services.storage_service import (
    GENERATION_JOB_DIR,
    resolve_generated_file,
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

            try:
                modified_day = datetime.fromtimestamp(file_path.stat().st_mtime).date()
            except FileNotFoundError:
                continue
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


def cleanup_old_generation_artifacts(days: int = 7) -> dict:
    """Delete old generation output files, job files, and matching DB rows."""
    from app.models import GenerationHistory
    from wsgi import db

    cutoff = datetime.utcnow() - timedelta(days=max(0, int(days)))
    summary = {
        "deleted_files": 0,
        "deleted_history_rows": 0,
        "deleted_job_files": 0,
    }

    old_generations = GenerationHistory.query.filter(
        GenerationHistory.generated_at < cutoff
    ).all()

    for generation in old_generations:
        for candidate in _generation_file_candidates(generation):
            if candidate.exists() and candidate.is_file():
                try:
                    candidate.unlink()
                    summary["deleted_files"] += 1
                except OSError as exc:
                    logger.warning("Could not delete old generation file %s: %s", candidate, exc)

        db.session.delete(generation)
        summary["deleted_history_rows"] += 1

    summary["deleted_files"] += _delete_old_files_in_dirs(cutoff)
    summary["deleted_job_files"] += _delete_old_generation_job_files(cutoff)
    db.session.commit()

    logger.info(
        "Generation cleanup complete: %s files, %s history rows, %s job files",
        summary["deleted_files"],
        summary["deleted_history_rows"],
        summary["deleted_job_files"],
    )
    return summary


def _generation_file_candidates(generation):
    candidates = []
    if generation.file_path:
        candidates.append(Path(generation.file_path))
    if generation.filename:
        resolved = resolve_generated_file(generation.filename)
        if resolved:
            candidates.append(resolved)
    return list(dict.fromkeys(candidates))


def _delete_old_files_in_dirs(cutoff: datetime) -> int:
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
            try:
                modified_at = datetime.fromtimestamp(file_path.stat().st_mtime)
            except FileNotFoundError:
                continue
            if modified_at >= cutoff:
                continue
            try:
                file_path.unlink()
                deleted_count += 1
            except OSError as exc:
                logger.warning("Could not delete old output file %s: %s", file_path, exc)
    return deleted_count


def _delete_old_generation_job_files(cutoff: datetime) -> int:
    deleted_count = 0
    if not GENERATION_JOB_DIR.exists():
        return 0

    for file_path in GENERATION_JOB_DIR.iterdir():
        if not file_path.is_file() or file_path.suffix.lower() not in {".json", ".cancel"}:
            continue
        try:
            modified_at = datetime.fromtimestamp(file_path.stat().st_mtime)
        except FileNotFoundError:
            continue
        if modified_at >= cutoff:
            continue
        try:
            file_path.unlink()
            deleted_count += 1
        except OSError as exc:
            logger.warning("Could not delete old generation job file %s: %s", file_path, exc)
    return deleted_count
