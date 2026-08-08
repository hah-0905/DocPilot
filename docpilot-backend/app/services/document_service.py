import asyncio
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models.documents import Document, DocumentChunk, DocumentVersion
from app.models.kb import KnowledgeBase
from app.services.document_parser import parse_document
from app.services.document_task_service import DocumentTaskService
from app.services.documents.document_delete_service import (
    DocumentDeleteService,
)
from app.services.documents.document_processing_service import (
    BackgroundTaskFactory,
    DocumentProcessingService,
    SessionFactory,
)
from app.services.documents.document_query_service import DocumentQueryService
from app.services.documents.document_storage import DocumentStorage
from app.services.documents.document_upload_service import DocumentUploadService
from app.services.llm_service import LLMService
from app.services.text_splitter import split_text
from app.services.vector_service import VectorService


class DocumentService:
    """Compatibility facade for document APIs and existing service callers."""

    def __init__(
        self,
        *,
        llm_service: LLMService | None = None,
        vector_service: VectorService | None = None,
        task_service: DocumentTaskService | None = None,
        storage: DocumentStorage | None = None,
        query_service: DocumentQueryService | None = None,
        session_factory: SessionFactory | None = None,
        background_task_factory: BackgroundTaskFactory = asyncio.create_task,
    ) -> None:
        self.llm_service = llm_service or LLMService()
        self.vector_service = vector_service or VectorService()
        self.task_service = task_service or DocumentTaskService()
        self.storage = storage or DocumentStorage(
            upload_root_factory=lambda: (
                Path(__file__).resolve().parents[2] / "uploads"
            )
        )
        self.query_service = query_service or DocumentQueryService()
        self.upload_service = DocumentUploadService(
            task_service=self.task_service,
            storage=self.storage,
        )
        self.delete_service = DocumentDeleteService(
            query_service=self.query_service,
            vector_service=self.vector_service,
        )
        self.processing_service = DocumentProcessingService(
            llm_service=self.llm_service,
            vector_service=self.vector_service,
            task_service=self.task_service,
            storage=self.storage,
            parser=lambda **kwargs: parse_document(**kwargs),
            splitter=lambda text: split_text(text),
            session_factory=session_factory,
            background_task_factory=background_task_factory,
        )

        # Preserve the legacy observable task set for compatibility.
        self._background_tasks = self.processing_service.background_tasks

    async def upload_documents(
        self,
        db: AsyncSession,
        user_id: int,
        kb_id: int,
        files: list[UploadFile],
    ) -> list[dict]:
        if not files:
            raise AppException(
                message="No files uploaded",
                code=400,
                status_code=400,
            )

        kb = await self._get_owned_knowledge_base(db, user_id, kb_id)
        uploaded: list[dict] = []
        for file in files:
            result = await self._save_uploaded_file(
                db=db,
                user_id=user_id,
                kb_id=kb.id,
                file=file,
            )
            uploaded.append(result)

        for item in uploaded:
            self._start_background_task(
                document_id=item["id"],
                version_id=item["version_id"],
                task_id=item["task_id"],
                kb_id=kb.id,
                filename=item["original_file_name"],
                storage_path=item["storage_path"],
            )
        return uploaded

    async def list_documents(
        self,
        db: AsyncSession,
        user_id: int,
        kb_id: int,
    ) -> list[Document]:
        return await self.query_service.list_documents(db, user_id, kb_id)

    async def count_chunks(
        self,
        db: AsyncSession,
        document_id: int,
        kb_id: int,
    ) -> int:
        return await self.query_service.count_chunks(
            db,
            document_id,
            kb_id,
        )

    async def list_document_chunks(
        self,
        db: AsyncSession,
        document_id: int,
        kb_id: int,
    ) -> list[DocumentChunk]:
        return await self.query_service.list_document_chunks(
            db,
            document_id,
            kb_id,
        )

    async def delete_document(
        self,
        db: AsyncSession,
        user_id: int,
        kb_id: int,
        document_id: int,
    ) -> bool:
        return await self.delete_service.delete_document(
            db=db,
            user_id=user_id,
            kb_id=kb_id,
            document_id=document_id,
        )

    async def _get_owned_knowledge_base(
        self,
        db: AsyncSession,
        user_id: int,
        kb_id: int,
    ) -> KnowledgeBase:
        return await self.query_service.get_owned_knowledge_base(
            db,
            user_id,
            kb_id,
        )

    async def get_document_version(
        self,
        db: AsyncSession,
        kb_id: int,
        document_id: int,
    ) -> DocumentVersion | None:
        return await self.query_service.get_document_version(
            db,
            kb_id,
            document_id,
        )

    async def get_document(
        self,
        db: AsyncSession,
        user_id: int,
        kb_id: int,
        document_id: int,
    ) -> Document | None:
        return await self.query_service.get_document(
            db,
            user_id,
            kb_id,
            document_id,
        )

    async def _save_uploaded_file(
        self,
        db: AsyncSession,
        user_id: int,
        kb_id: int,
        file: UploadFile,
    ) -> dict:
        return await self.upload_service.save_uploaded_file(
            db=db,
            user_id=user_id,
            kb_id=kb_id,
            file=file,
        )

    async def _process_document_in_background(
        self,
        document_id: int,
        version_id: int,
        task_id: str,
        kb_id: int,
        filename: str,
        storage_path: str,
    ) -> None:
        await self.processing_service.process_document(
            document_id=document_id,
            version_id=version_id,
            task_id=task_id,
            kb_id=kb_id,
            filename=filename,
            storage_path=storage_path,
        )

    async def _persist_document_failure(
        self,
        db: AsyncSession,
        document_id: int,
        version_id: int,
        stage: str,
        error_message: str,
    ) -> None:
        await self.processing_service.failure_service.persist_document_failure(
            db=db,
            document_id=document_id,
            version_id=version_id,
            stage=stage,
            error_message=error_message,
        )

    def _start_background_task(
        self,
        *,
        document_id: int,
        version_id: int,
        task_id: str,
        kb_id: int,
        filename: str,
        storage_path: str,
    ) -> None:
        self.processing_service.start_background_task(
            document_id=document_id,
            version_id=version_id,
            task_id=task_id,
            kb_id=kb_id,
            filename=filename,
            storage_path=storage_path,
        )
