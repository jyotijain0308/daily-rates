"""Shared filesystem paths for user-uploaded and generated artifacts."""
from pathlib import Path
from typing import List, Optional, Union


PROJECT_ROOT = Path(__file__).resolve().parents[2]
UPLOADS_ROOT = PROJECT_ROOT / "uploads"
GENERATED_ROOT = UPLOADS_ROOT / "generated"
GENERATED_VIDEO_DIR = GENERATED_ROOT / "videos"
GENERATED_PRESENTATION_DIR = GENERATED_ROOT / "presentations"
GENERATION_JOB_DIR = UPLOADS_ROOT / "jobs" / "generation"
ASSETS_ROOT = UPLOADS_ROOT / "assets"


def ensure_storage_dirs() -> None:
    """Create the upload-backed storage directories used by the app."""
    for directory in (
        UPLOADS_ROOT,
        GENERATED_VIDEO_DIR,
        GENERATED_PRESENTATION_DIR,
        GENERATION_JOB_DIR,
        ASSETS_ROOT,
    ):
        directory.mkdir(parents=True, exist_ok=True)


def resolve_asset_file(
    path_or_name: Optional[Union[str, Path]],
    extra_dirs: Optional[List[Path]] = None,
) -> Optional[Path]:
    """Resolve asset paths from uploads storage and legacy asset path formats."""
    if not path_or_name:
        return None

    raw_path = Path(path_or_name)
    candidates = []
    if raw_path.is_absolute():
        candidates.append(raw_path)
    else:
        candidates.append(PROJECT_ROOT / raw_path)
        if raw_path.parts and raw_path.parts[0] == "assets":
            candidates.append(UPLOADS_ROOT.joinpath(*raw_path.parts))
        if len(raw_path.parts) >= 2 and raw_path.parts[0] == "uploads" and raw_path.parts[1] == "assets":
            candidates.append(PROJECT_ROOT / raw_path)

        for directory in extra_dirs or []:
            candidates.append(directory / raw_path.name)

        candidates.extend([
            ASSETS_ROOT / raw_path.name,
            ASSETS_ROOT / "company" / raw_path.name,
            ASSETS_ROOT / "products" / raw_path.name,
            ASSETS_ROOT / "countries" / raw_path.name,
            ASSETS_ROOT / "countries" / "default" / raw_path.name,
        ])

    for candidate in dict.fromkeys(candidates):
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def generated_output_path(filename: str) -> Path:
    """Return the upload-backed output path for a generated filename."""
    suffix = Path(filename).suffix.lower()
    if suffix == ".mp4":
        return GENERATED_VIDEO_DIR / filename
    return GENERATED_PRESENTATION_DIR / filename


def generation_job_path(job_id: str, suffix: str = ".json") -> Path:
    """Return the current storage path for a generation job artifact."""
    return GENERATION_JOB_DIR / f"{job_id}{suffix}"


def resolve_generated_file(filename_or_path: Optional[Union[str, Path]]) -> Optional[Path]:
    """Resolve generated files from uploads storage."""
    if not filename_or_path:
        return None

    raw_path = Path(filename_or_path)
    candidates = []
    if raw_path.is_absolute():
        candidates.append(raw_path)
    else:
        candidates.extend([
            PROJECT_ROOT / raw_path,
            generated_output_path(raw_path.name),
            GENERATED_VIDEO_DIR / raw_path.name,
            GENERATED_PRESENTATION_DIR / raw_path.name,
        ])

    for candidate in dict.fromkeys(candidates):
        if candidate.exists() and candidate.is_file():
            return candidate
    return None
