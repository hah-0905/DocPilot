import hashlib
import logging
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models.documents import Document, DocumentVersion
from app.services.document_task_service import DocumentTaskService
from app.services.documents.document_storage import DocumentStorage


logger = logging.getLogger(__name__)


class DocumentUploadService:
    """Persist an uploaded original and its initial database records."""

    def __init__(
        self,
        *,
        task_service: DocumentTaskService,
        storage: DocumentStorage,
    ) -> None:
        self.task_service = task_service
        self.storage = storage

    async def save_uploaded_file(
        self,
        db: AsyncSession,
        user_id: int,
        kb_id: int,
        file: UploadFile,
    ) -> dict:
        """Save one original and commit its document, version, and task."""
        filename = file.filename or "unknown"
        storage_path: Path | None = None

        try:
            file_bytes = await file.read()
            if not file_bytes:
                raise AppException(
                    message=f"File is empty: {filename}",
                    code=400,
                    status_code=400,
                )

            file_ext = Path(filename).suffix.lower().lstrip(".")
            file_sha256 = hashlib.sha256(file_bytes).hexdigest()
            storage_path = self.storage.save(
                kb_id=kb_id,
                filename=filename,
                file_sha256=file_sha256,
                file_bytes=file_bytes,
            )

            document = Document(
                kb_id=kb_id,
                title=filename,
                original_file_name=filename,
                file_ext=file_ext or None,
                size_bytes=len(file_bytes),
                sha256=file_sha256,
                mime_type=file.content_type,
                parse_status="pending",
                index_status="not_indexed",
                created_by=user_id,
            )
            db.add(document)
            await db.flush()

            version = DocumentVersion(
                document_id=document.id,
                version_no=1,
                storage_uri=str(storage_path),
                original_file_name=filename,
                sha256=file_sha256,
                parser_name="builtin",
                parser_version="1",
                parser_config={},
                char_count=None,
                token_count=None,
                status="pending",
                created_by=user_id,
            )
            db.add(version)
            await db.flush()

            document.current_version_id = version.id
            processing_task = await self.task_service.create_task(
                db=db,
                kb_id=kb_id,
                document_id=document.id,
                version_id=version.id,
                created_by=user_id,
            )

            await db.commit()

            cache_created = await self.task_service.cache_task_by_id(
                processing_task.task_id,
                force_latest=True,
            )
            if not cache_created:
                logger.warning(
                    "Initial task cache creation failed: task_id=%s",
                    processing_task.task_id,
                )

            logger.info(
                "Document saved (pending processing): document_id=%s, "
                "version_id=%s, kb_id=%s, filename=%s",
                document.id,
                version.id,
                kb_id,
                filename,
            )

            return {
                "id": document.id,
                "version_id": version.id,
                "task_id": processing_task.task_id,
                "kb_id": document.kb_id,
                "title": document.title,
                "original_file_name": document.original_file_name,
                "file_ext": document.file_ext,
                "mime_type": document.mime_type,
                "size_bytes": document.size_bytes,
                "sha256": document.sha256,
                "current_version_id": document.current_version_id,
                "parse_status": document.parse_status,
                "index_status": document.index_status,
                "storage_path": str(storage_path),
            }

        except AppException:
            raise
        except Exception as exc:
            await db.rollback()
            if storage_path is not None:
                try:
                    self.storage.delete(storage_path)
                except OSError:
                    logger.exception(
                        "Failed to remove upload after database failure: "
                        "storage_path=%s",
                        storage_path,
                    )
            raise AppException(
                message=f"Failed to save file: {filename} - {exc}",
                code=500,
                status_code=500,
            ) from exc
