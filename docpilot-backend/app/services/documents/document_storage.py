from collections.abc import Callable
from pathlib import Path


class DocumentStorage:
    """Store and read original uploaded files under a configurable root."""

    def __init__(
        self,
        upload_root: Path | None = None,
        *,
        upload_root_factory: Callable[[], Path] | None = None,
    ) -> None:
        if upload_root is not None and upload_root_factory is not None:
            raise ValueError(
                "upload_root and upload_root_factory are mutually exclusive"
            )
        self._upload_root = upload_root
        self._upload_root_factory = upload_root_factory

    @property
    def upload_root(self) -> Path:
        if self._upload_root is not None:
            return self._upload_root
        if self._upload_root_factory is None:
            raise RuntimeError("Document upload root is not configured")
        return self._upload_root_factory()

    def save(
        self,
        *,
        kb_id: int,
        filename: str,
        file_sha256: str,
        file_bytes: bytes,
    ) -> Path:
        upload_dir = self.upload_root / str(kb_id)
        upload_dir.mkdir(parents=True, exist_ok=True)

        safe_name = Path(filename).name
        storage_path = upload_dir / f"{file_sha256}_{safe_name}"
        storage_path.write_bytes(file_bytes)
        return storage_path

    def read(self, storage_path: str, filename: str) -> bytes:
        source_path = Path(storage_path)
        if not source_path.exists():
            raise FileNotFoundError(
                f"Stored document file not found: {storage_path}"
            )

        file_bytes = source_path.read_bytes()
        if not file_bytes:
            raise ValueError(f"Stored document file is empty: {filename}")
        return file_bytes

    def delete(self, storage_path: Path) -> None:
        if storage_path.exists():
            storage_path.unlink()
