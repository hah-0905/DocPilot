from pathlib import Path

from app.core.config import Settings


def data_directories(settings: Settings) -> tuple[Path, Path, Path, Path]:
    """Create and return the configured, absolute application data directories."""
    directories = tuple(
        Path(value).expanduser().resolve()
        for value in (
            settings.upload_dir,
            settings.export_dir,
            settings.chroma_persist_dir,
            settings.log_dir,
        )
    )
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
    return directories  # type: ignore[return-value]


def path_in_directory(root: Path, candidate: Path) -> Path:
    """Resolve a path and reject paths that escape the configured storage root."""
    resolved_root = root.expanduser().resolve()
    resolved_candidate = candidate.expanduser().resolve()
    try:
        resolved_candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError("Path is outside the configured storage directory") from exc
    return resolved_candidate
