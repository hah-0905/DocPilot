import asyncio
import logging
from collections.abc import Callable, Coroutine
from typing import Any, AsyncContextManager

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.documents import Document, DocumentVersion
from app.services.document_task_service import DocumentTaskService
from app.services.documents.document_chunk_indexer import (
    DocumentChunkIndexer,
    DocumentProcessingState,
)
from app.services.documents.document_failure_service import (
    DocumentFailureService,
)
from app.services.documents.document_storage import DocumentStorage
from app.services.llm_service import LLMService
from app.services.vector_service import VectorService


logger = logging.getLogger(__name__)

SessionFactory = Callable[[], AsyncContextManager[AsyncSession]]
BackgroundTaskFactory = Callable[
    [Coroutine[Any, Any, None]],
    asyncio.Task[None],
]


class DocumentProcessingService:
    """Run and track the parse, split, embed, and index pipeline."""

    def __init__(
        self,
        *,
        llm_service: LLMService,
        vector_service: VectorService,
        task_service: DocumentTaskService,
        storage: DocumentStorage,
        parser: Callable[..., str],
        splitter: Callable[[str], list[str]],
        session_factory: SessionFactory | None = None,
        background_task_factory: BackgroundTaskFactory = asyncio.create_task,
    ) -> None:
        self.task_service = task_service
        self.storage = storage
        self.parser = parser
        self.splitter = splitter
        self.session_factory = session_factory
        self.background_task_factory = background_task_factory
        self.chunk_indexer = DocumentChunkIndexer(
            llm_service=llm_service,
            vector_service=vector_service,
            task_service=task_service,
        )
        self.failure_service = DocumentFailureService(
            vector_service=vector_service,
            task_service=task_service,
        )
        self.background_tasks: set[asyncio.Task[None]] = set()

    def _get_session_factory(self) -> SessionFactory:
        if self.session_factory is not None:
            return self.session_factory

        from app.db.session import AsyncSessional

        return AsyncSessional

    async def process_document(
        self,
        document_id: int,
        version_id: int,
        task_id: str,
        kb_id: int,
        filename: str,
        storage_path: str,
    ) -> None:
        state = DocumentProcessingState(task_id=task_id)
        session_factory = self._get_session_factory()

        async with session_factory() as db:
            try:
                await self.task_service.mark_running(
                    task_id,
                    stage="parsing",
                    progress=5,
                )

                document = await db.get(Document, document_id)
                version = await db.get(DocumentVersion, version_id)
                if document is None or version is None:
                    error_message = (
                        "Document or version not found: "
                        f"document_id={document_id}, version_id={version_id}"
                    )
                    logger.error(error_message)
                    await self.task_service.mark_failed(
                        task_id,
                        stage="parsing",
                        error_code="DOCUMENT_NOT_FOUND",
                        error_message=error_message,
                    )
                    return

                document.parse_status = "processing"
                document.index_status = "not_indexed"
                version.status = "processing"
                version.error_message = None
                await db.commit()

                state.stage = "parsing"
                file_bytes = self.storage.read(storage_path, filename)
                text = self.parser(
                    filename=filename,
                    file_bytes=file_bytes,
                )
                if not text.strip():
                    raise ValueError(
                        "Document content is empty after parsing: "
                        f"{filename}"
                    )

                version.char_count = len(text)
                version.token_count = None

                state.stage = "splitting"
                await self.task_service.update_progress(
                    task_id,
                    stage="splitting",
                    progress=20,
                )
                chunks = self.splitter(text)
                if not chunks:
                    raise ValueError(
                        "Document content is empty after splitting: "
                        f"{filename}"
                    )
                state.total_chunks = len(chunks)

                document.parse_status = "success"
                document.index_status = "indexing"
                version.status = "success"
                version.error_message = None
                await db.commit()

                logger.info(
                    "Document parsed and split: document_id=%s, "
                    "task_id=%s, chunk_count=%s",
                    document.id,
                    task_id,
                    state.total_chunks,
                )

                state.stage = "embedding"
                await self.task_service.update_progress(
                    task_id,
                    stage="embedding",
                    progress=35,
                    total_chunks=state.total_chunks,
                    processed_chunks=0,
                    failed_chunks=0,
                )
                await self.chunk_indexer.index_chunks(
                    db=db,
                    document=document,
                    version=version,
                    kb_id=kb_id,
                    filename=filename,
                    chunks=chunks,
                    state=state,
                )
                await db.flush()

                state.stage = "finalizing"
                await self.task_service.update_progress(
                    task_id,
                    stage="finalizing",
                    progress=95,
                    total_chunks=state.total_chunks,
                    processed_chunks=state.processed_chunks,
                    failed_chunks=0,
                )

                if state.processed_chunks != state.total_chunks:
                    raise RuntimeError(
                        "Processed chunk count mismatch: "
                        f"expected={state.total_chunks}, "
                        f"actual={state.processed_chunks}"
                    )
                if len(state.inserted_vector_ids) != state.total_chunks:
                    raise RuntimeError(
                        "Vector count mismatch: "
                        f"expected={state.total_chunks}, "
                        f"actual={len(state.inserted_vector_ids)}"
                    )

                document.index_status = "indexed"
                version.error_message = None
                await db.commit()

                task_updated = await self.task_service.mark_success(
                    task_id,
                    total_chunks=state.total_chunks,
                )
                if not task_updated:
                    logger.error(
                        "Document completed but task success update failed: "
                        "document_id=%s, task_id=%s",
                        document_id,
                        task_id,
                    )

                logger.info(
                    "Document indexed successfully: document_id=%s, "
                    "task_id=%s, chunk_count=%s, vector_count=%s",
                    document.id,
                    task_id,
                    state.total_chunks,
                    len(state.inserted_vector_ids),
                )

            except Exception as exc:
                logger.exception(
                    "Background document processing failed: filename=%s, "
                    "document_id=%s, task_id=%s, stage=%s",
                    filename,
                    document_id,
                    task_id,
                    state.stage,
                )
                await self.failure_service.handle_processing_failure(
                    db=db,
                    document_id=document_id,
                    version_id=version_id,
                    state=state,
                    error=exc,
                )

    def start_background_task(
        self,
        *,
        document_id: int,
        version_id: int,
        task_id: str,
        kb_id: int,
        filename: str,
        storage_path: str,
    ) -> None:
        task = self.background_task_factory(
            self.process_document(
                document_id=document_id,
                version_id=version_id,
                task_id=task_id,
                kb_id=kb_id,
                filename=filename,
                storage_path=storage_path,
            )
        )
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)
