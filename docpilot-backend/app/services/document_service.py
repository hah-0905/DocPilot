from datetime import datetime, timezone
import hashlib
from typing import List
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import String, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import AppException
from app.core.config import get_settings
from app.core.storage import path_in_directory
from app.models.chunk_embeddings import ChunkEmbedding
from app.models.documents import Document, DocumentChunk, DocumentVersion
from app.models.kb import KnowledgeBase
from app.models.workspaces import Workspace
from app.services.document_parser import parse_document
from app.services.llm_service import LLMService
from app.services.text_splitter import split_text
from app.services.vector_service import VectorService


class DocumentService:
    def __init__(self) -> None:
        self.llm_service = LLMService()
        self.vector_service = VectorService()

    async def upload_documents(
        self,
        db: AsyncSession,
        user_id: int,
        kb_id: int,
        files: list[UploadFile],
    ) -> list[dict]:
        """
        Upload files, parse text, create document versions, and persist chunks.
        """
        if not files:
            raise AppException(
                message="No files uploaded",
                code=400,
                status_code=400,
            )

        kb = await self._get_owned_knowledge_base(db, user_id, kb_id)
        uploaded: list[dict] = []

        try:
            for file in files:
                uploaded.append(
                    await self._upload_one_file(
                        db=db,
                        user_id=user_id,
                        kb_id=kb.id,
                        file=file,
                    )
                )

            await db.commit()
            return uploaded

        except AppException:
            await db.rollback()
            raise
        except Exception as exc:
            await db.rollback()
            raise AppException(
                message=f"Document upload failed: {exc}",
                code=500,
                status_code=500,
            ) from exc

    async def list_documents(
            self,
            db: AsyncSession,
            user_id: int,
            kb_id: int,
    ) -> list[Document]:
        kb = await self._get_owned_knowledge_base(db, user_id, kb_id)

        result = await db.execute(
            select(Document).where(
                Document.kb_id == kb.id,
            )
        )
        return result.scalars().all()

    async def count_chunks(
            self,
            db: AsyncSession,
            document_id: int,
            kb_id: int,
    ):
        count = await db.execute(
            select(func.count()).select_from(DocumentChunk).where(
                DocumentChunk.kb_id == kb_id,
                DocumentChunk.document_id == document_id,
            )
        )
        return count.scalar_one()

    async def list_document_chunks(
            self,
            db: AsyncSession,
            document_id: int,
            kb_id: int,
    ) -> list[DocumentChunk]:
        result = await db.execute(
            select(DocumentChunk).where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.kb_id == kb_id,
                DocumentChunk.enabled == True,
            ).order_by(DocumentChunk.chunk_no.asc())
        )
        return result.scalars().all()

    async def delete_document(
            self,
            db: AsyncSession,
            user_id: int,
            kb_id: int,
            document_id: int,
    ):
        await self._get_owned_knowledge_base(db, user_id, kb_id)

        result = await db.execute(
            select(ChunkEmbedding.vector_id).where(
                ChunkEmbedding.kb_id == kb_id,
                ChunkEmbedding.chunk_id.in_(
                    select(DocumentChunk.id).where(
                        DocumentChunk.document_id == document_id,
                        DocumentChunk.kb_id == kb_id,
                    )
                ),
            )
        )
        vector_ids = list(result.scalars().all())
        if vector_ids:
            await self.vector_service.delete_vectors(vector_ids)

        deleted_at = datetime.now(timezone.utc)

        await db.execute(
            update(DocumentChunk).where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.kb_id == kb_id,
            ).values(
                enabled=False,
            )
        )

        await db.execute(
            update(DocumentVersion).where(
                DocumentVersion.document_id == document_id,
            ).values(
                status="deleted",
            )
        )

        await db.execute(
            update(Document).where(
                Document.id == document_id,
                Document.kb_id == kb_id,
            ).values(
                deleted_at=deleted_at,
                enabled=False,
            )
        )

        await db.commit()
        return True

    async def _get_owned_knowledge_base(
        self,
        db: AsyncSession,
        user_id: int,
        kb_id: int,
    ) -> KnowledgeBase:
        result = await db.execute(
            select(KnowledgeBase).join(Workspace).where(
                KnowledgeBase.id == kb_id,
                Workspace.owner_user_id == user_id,
                Workspace.status == "active",
                KnowledgeBase.status == "active",
            )
        )
        kb = result.scalar_one_or_none()
        if not kb:
            raise AppException(
                message="Knowledge base does not exist",
                code=404,
                status_code=404,
            )
        return kb

    async def get_document_version(
        self,
        db: AsyncSession,
        kb_id: int,
        document_id: int,
    ) -> List[DocumentVersion]:
        result = await db.execute(
            select(DocumentVersion).join(
                Document, DocumentVersion.document_id == Document.id
            ).where(
                Document.id == document_id,
                Document.kb_id == kb_id,
                Document.deleted_at.is_(None),
                Document.enabled == True
            )
            .order_by(DocumentVersion.version_no.desc())
        )
        version = result.scalar_one_or_none()
        return version
    
    async def get_document(
            self,
            db: AsyncSession,
            user_id: int,
            kb_id: int,
            document_id: int,
    ) -> Document | None:
        await self._get_owned_knowledge_base(db, user_id, kb_id)

        document = await db.execute(
            select(Document).where(
                Document.id == document_id,
                Document.kb_id == kb_id,
                Document.deleted_at.is_(None),
                Document.enabled == True
            )
        )
        return document.scalar_one_or_none()

    async def _upload_one_file(
        self,
        db: AsyncSession,
        user_id: int,
        kb_id: int,
        file: UploadFile,
    ) -> dict:
        filename = Path(file.filename or "unknown").name
        file_bytes = await file.read()

        if not file_bytes:
            raise AppException(
                message=f"File is empty: {filename}",
                code=400,
                status_code=400,
            )

        try:
            text = parse_document(filename, file_bytes)
        except ValueError as exc:
            raise AppException(
                message=str(exc),
                code=400,
                status_code=400,
            ) from exc

        chunks = split_text(text)
        if not chunks:
            raise AppException(
                message=f"Document content is empty: {filename}",
                code=400,
                status_code=400,
            )

        file_ext = Path(filename).suffix.lower().lstrip(".")
        file_sha256 = hashlib.sha256(file_bytes).hexdigest()

        upload_root = Path(get_settings().upload_dir).expanduser().resolve()
        upload_dir = upload_root / str(kb_id)
        upload_dir.mkdir(parents=True, exist_ok=True)

        stored_name = f"{file_sha256}_{filename}"
        storage_path = path_in_directory(upload_root, upload_dir / stored_name)

        storage_path.write_bytes(file_bytes)

        document = Document(
            kb_id=kb_id,
            title=filename,
            original_file_name=filename,
            file_ext=file_ext or None,
            size_bytes=len(file_bytes),
            sha256=file_sha256,
            mime_type=file.content_type,
            parse_status="processing",
            index_status="indexing",
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
            char_count=len(text),
            token_count=len(text),
            status="success",
            created_by=user_id,
        )
        db.add(version)
        await db.flush()

        document.current_version_id = version.id
        document.parse_status = "success"
        document.index_status = "indexed"

        for index, chunk in enumerate(chunks, start=1):
            chunk_hash = hashlib.sha256(chunk.encode("utf-8")).hexdigest()
            document_chunk = DocumentChunk(
                kb_id=kb_id,
                document_id=document.id,
                version_id=version.id,
                chunk_no=index,
                chunk_uid=str(uuid.uuid4()),
                content=chunk,
                content_hash=chunk_hash,
                char_count=len(chunk),
                token_count=len(chunk),
                metadata_={"file_sha256": file_sha256},
            )
            db.add(document_chunk)
            await db.flush()

            embedding = await self.llm_service.embed_text(chunk)
            vector_id = str(document_chunk.id)
            await self.vector_service.upsert_chunk_vector(
                vector_id=vector_id,
                embedding=embedding,
                metadata={
                    "kb_id": kb_id,
                    "chunk_id": document_chunk.id,
                    "document_id": document.id,
                    "content_hash": chunk_hash,
                },
            )

            db.add(
                ChunkEmbedding(
                    kb_id=kb_id,
                    chunk_id=document_chunk.id,
                    vector_store_type=self.vector_service.vector_store_type,
                    vector_collection=self.vector_service.vector_collection,
                    vector_id=vector_id,
                    embedding_model=self.llm_service.embedding_model,
                    embedding_dim=len(embedding),
                    content_hash=chunk_hash,
                    status="active",
                )
            )

        return {
            "id": document.id,
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
            "chunk_count": len(chunks),
        }
