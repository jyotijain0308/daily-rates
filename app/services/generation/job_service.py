"""File-backed MP4 generation job state and cancellation."""
import json
import logging
import threading
import uuid
from datetime import datetime

from app.services.storage_service import (
    GENERATION_JOB_DIR,
    generation_job_path,
)

logger = logging.getLogger(__name__)

JOBS_DIR = GENERATION_JOB_DIR


def _job_path(job_id):
    return generation_job_path(job_id, ".json")


def _cancel_path(job_id):
    return generation_job_path(job_id, ".cancel")


def _now():
    return datetime.utcnow().isoformat()


def _write_job(job_id, data):
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    data = {**data, "job_id": job_id, "updated_at": _now()}
    path = _job_path(job_id)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def create_job(country, shipment_by, product_count, company_id=None):
    job_id = uuid.uuid4().hex
    return _write_job(job_id, {
        "status": "queued",
        "company_id": company_id,
        "country": country,
        "shipment_by": shipment_by,
        "product_count": product_count,
        "message": "Queued",
        "created_at": _now(),
        "result": None,
        "error": None,
    })


def read_job(job_id):
    path = _job_path(job_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_generation_jobs(company_id=None, statuses=None, updated_since=None):
    """Return stored generation jobs, optionally filtered by company and status."""
    if not JOBS_DIR.exists():
        return []

    allowed_statuses = set(statuses or [])
    jobs = []
    for path in JOBS_DIR.glob("*.json"):
        try:
            job = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning("Could not read generation job file: %s", path)
            continue

        if company_id is not None and job.get("company_id") != company_id:
            continue
        if allowed_statuses and job.get("status") not in allowed_statuses:
            continue
        if updated_since and _parse_job_datetime(job.get("updated_at")) < updated_since:
            continue
        jobs.append(job)

    return sorted(jobs, key=lambda item: item.get("updated_at") or "", reverse=True)


def _parse_job_datetime(value):
    if not value:
        return datetime.min
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return datetime.min


def update_job(job_id, **fields):
    current = read_job(job_id) or {"created_at": _now()}
    current.update(fields)
    return _write_job(job_id, current)


def request_cancel(job_id):
    if not read_job(job_id):
        return False
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    _cancel_path(job_id).write_text("cancel", encoding="utf-8")
    current = read_job(job_id)
    if current and current.get("status") in {"queued", "running"}:
        update_job(job_id, message="Cancellation requested")
    return True


def is_cancel_requested(job_id):
    return _cancel_path(job_id).exists()


def start_generation_job(
    app,
    job_id,
    country,
    shipment_by,
    audio_path=None,
    company_id=None,
    generation_date=None,
    content_fingerprint=None,
):
    thread = threading.Thread(
        target=_run_generation_job,
        args=(app, job_id, country, shipment_by, audio_path, company_id, generation_date, content_fingerprint),
        daemon=True,
    )
    thread.start()
    return thread


def _run_generation_job(
    app,
    job_id,
    country,
    shipment_by,
    audio_path=None,
    company_id=None,
    generation_date=None,
    content_fingerprint=None,
):
    with app.app_context():
        try:
            from app.services.ppt_service import GenerationCancelled, PPTGenerationService

            update_job(job_id, status="running", message="Generating MP4")
            success, result, error_msg = PPTGenerationService.generate_ppt(
                country_filter=country,
                shipment_filter=shipment_by,
                output_format="mp4",
                background_audio_path=audio_path,
                company_id=company_id,
                generation_date=generation_date,
                content_fingerprint=content_fingerprint,
                is_cancelled=lambda: is_cancel_requested(job_id),
            )

            if success:
                update_job(job_id, status="completed", message="MP4 generated", result=result, error=None)
            else:
                update_job(job_id, status="failed", message=error_msg, error=error_msg)
        except GenerationCancelled as exc:
            logger.info("Generation job cancelled: %s", job_id)
            update_job(job_id, status="cancelled", message=str(exc), error=None)
        except Exception as exc:
            logger.exception("Generation job failed: %s", job_id)
            update_job(job_id, status="failed", message=str(exc), error=str(exc))
