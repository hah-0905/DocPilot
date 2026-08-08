import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.documents import Document, DocumentVersion
from app.services.document_task_service import DocumentTaskService
from app.services.documents.document_chunk_indexer import (
    DocumentProcessingState,
)
from app.services.vector_service import VectorService


logger = logging.getLogger(__name__)


class DocumentFailureService:
    """Persist processing failures and compensate non-transactional vectors."""

    ERROR_CODE_BY_STAGE = {
        "parsing": "DOCUMENT_PARSE_FAILED",
        "splitting": "TEXT_SPLIT_FAILED",
        "embedding": "EMBEDDING_FAILED",
        "vector_upserting": "VECTOR_UPSERT_FAILED",
        "finalizing": "DOCUMENT_FINALIZATION_FAILED",
    }

    def __init__(
        self,
        *,
        vector_service: VectorService,
        task_service: DocumentTaskService,
    ) -> None:
        self.vector_service = vector_service
        self.task_service = task_service

    async def handle_processing_failure(
        self,
        *,
        db: AsyncSession,
        document_id: int,
        version_id: int,
        state: DocumentProcessingState,
        error: Exception,
    ) -> None:
        await db.rollback()

        if state.inserted_vector_ids:
            try:
                await self.vector_service.delete_vectors(
                    state.inserted_vector_ids
                )
            except Exception:
                logger.exception(
                    "Failed to clean up Chroma vectors: "
                    "document_id=%s, task_id=%s, vector_ids=%s",
                    document_id,
                    state.task_id,
                    state.inserted_vector_ids,
                )

        await self.persist_document_failure(
            db=db,
            document_id=document_id,
            version_id=version_id,
            stage=state.stage,
            error_message=str(error),
        )

        await self.task_service.mark_failed(
            state.task_id,
            stage=state.stage,
            error_code=self.ERROR_CODE_BY_STAGE.get(
                state.stage,
                "DOCUMENT_PROCESSING_FAILED",
            ),
            error_message=str(error),
        )

    async def persist_document_failure(
        self,
        db: AsyncSession,
        document_id: int,
        version_id: int,
        stage: str,
        error_message: str,
    ) -> None:
        """Persist the same parse/index failure state as the legacy service."""
        try:
            document = await db.get(Document, document_id)
            version = await db.get(DocumentVersion, version_id)

            if document is None:
                logger.error(
                    "Cannot persist failure status: document_id=%s not found",
                    document_id,
                )
                return
            if version is None:
                logger.error(
                    "Cannot persist failure status: version_id=%s not found",
                    version_id,
                )
                return

            if stage in {"parsing", "splitting"}:
                document.parse_status = "failed"
                document.index_status = "not_indexed"
                version.status = "failed"
            else:
                if document.parse_status != "success":
                    document.parse_status = "failed"
                    version.status = "failed"
                document.index_status = "failed"

            version.error_message = f"[stage={stage}] {error_message}"
            await db.commit()

            logger.info(
                "Document failure status persisted: document_id=%s, "
                "parse_status=%s, index_status=%s, stage=%s",
                document.id,
                document.parse_status,
                document.index_status,
                stage,
            )

        except Exception:
            await db.rollback()
            logger.exception(
                "Failed to persist document failure status: "
                "document_id=%s, version_id=%s",
                document_id,
                version_id,
            )
