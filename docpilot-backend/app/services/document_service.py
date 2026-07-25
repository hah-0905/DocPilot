from datetime import datetime, timezone
import hashlib
from typing import List
import uuid
from pathlib import Path
import logging
from fastapi import UploadFile
from sqlalchemy import String, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import AppException
from app.models.chunk_embeddings import ChunkEmbedding
from app.models.documents import Document, DocumentChunk, DocumentVersion
from app.models.kb import KnowledgeBase
from app.models.workspaces import Workspace
from app.services.document_parser import parse_document
from app.services.llm_service import LLMService
from app.services.text_splitter import split_text
from app.services.vector_service import VectorService

logger = logging.getLogger(__name__)

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

        for file in files:
            result = await self.uploaded.append(
                await self._upload_one_file(
                    db=db,
                    user_id=user_id,
                    kb_id=kb.id,
                    file=file,
                )
            )
            uploaded.append(result)
        
        return uploaded

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
        filename = file.filename or "unknown"
        document_id: int | None = None
        version_id: int | None = None
        storage_path: Path | None = None
        inserted_vector_ids: list[str] = []
        current_stage = "validating"

        try:
            # ------------------------------------------------------------
            # 1. 读取并校验文件
            # ------------------------------------------------------------
            file_bytes = await file.read()

            if not file_bytes:
                raise AppException(
                    message=f"File is empty: {filename}",
                    code=400,
                    status_code=400,
                )

            file_ext = Path(filename).suffix.lower().lstrip(".")
            file_sha256 = hashlib.sha256(file_bytes).hexdigest()


            # ------------------------------------------------------------
            # 2. 保存原始文件
            # ------------------------------------------------------------
            current_stage = "creating_document"

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

            document_id = document.id

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

            version_id = version.id
            document.current_version_id = version.id

            # 初始记录必须先提交。
            # 后续解析失败时，Document 才不会被整个事务回滚掉。
            await db.commit()

            logger.info(
                "Document record created: document_id=%s, version_id=%s, "
            "kb_id=%s, filename=%s",
            document_id, 
            version_id, 
            kb_id, 
            filename
            )

            # ------------------------------------------------------------
            # 4. 文档解析
            # ------------------------------------------------------------
            current_stage = "parsing"

            document.parse_status = "processing"
            version.status = "processing"
            version.error_message = None
            await db.commit()

            text = parse_document(filename=filename, file_bytes=file_bytes)

            if not text.strip():
                raise ValueError(
                    f"Document content is empty after parsing: {filename}"
                )

            version.char_count = len(text)
            
            # 当前项目暂时没有真正的 tokenizer。
            # 为避免把字符数伪装成 token 数，阶段一先不填写。
            version.token_count = None

            # ------------------------------------------------------------
            # 5. 文本切分
            # ------------------------------------------------------------
            current_stage = "splitting"

            chunks = split_text(text)

            if not chunks:
                raise ValueError(
                    f"Document content is empty after splitting: {filename}"
                )

            # 解析和切分均成功。
            document.parse_status = "success"
            document.index_status = "indexing"
            version.status = "success"
            version.error_message = None

            # 提交解析结果和 indexing 状态。
            await db.commit()

            logger.info(
                "Document parsed and split: document_id=%s, chunk_count=%s",
                document.id,
                len(chunks),
            )

            # ------------------------------------------------------------
            # 6. Chunk、Embedding、向量入库
            # ------------------------------------------------------------
            current_stage = "indexing"

            for index, chunk in enumerate(chunks, start=1):
                chunk_hash = hashlib.sha256(
                    chunk.encode("utf-8")
                ).hexdigest()
                document_chunk = DocumentChunk(
                    kb_id=kb_id,
                    document_id=document.id,
                    version_id=version.id,
                    chunk_no=index,
                    chunk_uid=str(uuid.uuid4()),
                    content=chunk,
                    content_hash=chunk_hash,
                    char_count=len(chunk),
                    token_count=None,
                    metadata_={
                        "file_sha256": file_sha256,
                        "source_file_name": filename,
                    },
                )
                db.add(document_chunk)
                await db.flush()

                # 生成 Embedding
                embedding = await self.llm_service.embed_text(chunk)

                if not embedding:
                    raise RuntimeError(
                        f"Embedding result is empty, chunk_id={document_chunk.id}"
                    )

                # 阶段一保留现有 vector_id 规则，避免影响已有检索逻辑。
                vector_id = str(document_chunk.id)

                # 写入 Chroma
                await self.vector_service.upsert_chunk_vector(
                    vector_id=vector_id,
                    embedding=embedding,
                    metadata={
                        "kb_id": kb_id,
                        "chunk_id": document_chunk.id,
                        "document_id": document.id,
                        "version_id": version.id,
                        "content_hash": chunk_hash,
                    },
                )
                inserted_vector_ids.append(vector_id)

                # 保存 MySQL 与 Chroma 的映射
                chunk_embedding = ChunkEmbedding(
                    kb_id=kb_id,
                    chunk_id=document_chunk.id,
                    vector_store_type=(
                        self.vector_service.vector_store_type
                    ),
                    vector_collection=(
                        self.vector_service.vector_collection
                    ),
                    vector_id=vector_id,
                    embedding_model=self.llm_service.embedding_model,
                    embedding_dim=len(embedding),
                    content_hash=chunk_hash,
                    status="active",
                )
                db.add(chunk_embedding)

            # 确保所有 ChunkEmbedding 已写入当前数据库事务。
            await db.flush()


            # ------------------------------------------------------------
            # 7. 只有全部完成后，才能设置 indexed
            # ------------------------------------------------------------
            current_stage = "finalizing"

            document.index_status = "indexed"
            version.error_message = None
    
            await db.commit()
    
            logger.info(
                "Document indexed successfully: document_id=%s, "
                "chunk_count=%s, vector_count=%s",
                document.id,
                len(chunks),
                len(inserted_vector_ids),
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
    
        except Exception as exc:
            logger.exception(
                "Document processing failed: filename=%s, "
                "document_id=%s, stage=%s",
                filename,
                document_id,
                current_stage,
            )
    
            # 回滚尚未提交的 Chunk 和 ChunkEmbedding。
            await db.rollback()
    
            # Chroma 不参与 MySQL 事务。
            # 已经写入的向量必须单独清理。
            if inserted_vector_ids:
                try:
                    await self.vector_service.delete_vectors(
                        inserted_vector_ids
                    )
                except Exception:
                    logger.exception(
                        "Failed to clean up Chroma vectors: "
                        "document_id=%s, vector_ids=%s",
                        document_id,
                        inserted_vector_ids,
                    )
    
            # 如果已经创建文档记录，则持久化失败状态。
            if document_id is not None and version_id is not None:
                await self._persist_document_failure(
                    db=db,
                    document_id=document_id,
                    version_id=version_id,
                    stage=current_stage,
                    error_message=str(exc),
                )
            else:
                # Document 尚未创建成功时，删除可能残留的原始文件。
                if storage_path is not None and storage_path.exists():
                    try:
                        storage_path.unlink()
                    except OSError:
                        logger.exception(
                            "Failed to delete orphan upload file: %s",
                            storage_path,
                        )
    
            if isinstance(exc, AppException):
                raise
            
            if isinstance(exc, ValueError):
                raise AppException(
                    message=str(exc),
                    code=400,
                    status_code=400,
                ) from exc
    
            raise AppException(
                message=f"Document processing failed at {current_stage}",
                code=500,
                status_code=500,
            ) from exc

    async def _persist_document_failure(
        self,
        db: AsyncSession,
        document_id: int,
        version_id: int,
        stage: str,
        error_message: str,
    ) -> None:
        """
        将文档处理失败状态保存到 MySQL。
    
        parsing / splitting：
            parse_status=failed
            index_status=not_indexed
    
        indexing / finalizing：
            parse_status 保持 success
            index_status=failed
        """
        try:
            document = await db.get(Document, document_id)
            version = await db.get(DocumentVersion, version_id)
    
            if document is None:
                logger.error(
                    "Cannot persist failure status: "
                    "document_id=%s not found",
                    document_id,
                )
                return
    
            if version is None:
                logger.error(
                    "Cannot persist failure status: "
                    "version_id=%s not found",
                    version_id,
                )
                return
    
            parse_failure_stages = {
                "parsing",
                "splitting",
            }
    
            if stage in parse_failure_stages:
                document.parse_status = "failed"
                document.index_status = "not_indexed"
                version.status = "failed"
            else:
                # 文件已经解析和切分成功，仅索引失败。
                if document.parse_status != "success":
                    document.parse_status = "failed"
                    version.status = "failed"
    
                document.index_status = "failed"
    
            version.error_message = (
                f"[stage={stage}] {error_message}"
            )
    
            await db.commit()
    
            logger.info(
                "Document failure status persisted: "
                "document_id=%s, parse_status=%s, "
                "index_status=%s, stage=%s",
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