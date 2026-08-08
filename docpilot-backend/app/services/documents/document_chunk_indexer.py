import hashlib
import uuid
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk_embeddings import ChunkEmbedding
from app.models.documents import Document, DocumentChunk, DocumentVersion
from app.services.document_task_service import DocumentTaskService
from app.services.llm_service import LLMService
from app.services.vector_service import VectorService


@dataclass
class DocumentProcessingState:
    """Mutable state needed for progress reporting and compensation."""

    task_id: str
    stage: str = "parsing"
    total_chunks: int = 0
    processed_chunks: int = 0
    inserted_vector_ids: list[str] = field(default_factory=list)


class DocumentChunkIndexer:
    """Create chunks, embed them, and persist their vector mappings."""

    def __init__(
        self,
        *,
        llm_service: LLMService,
        vector_service: VectorService,
        task_service: DocumentTaskService,
    ) -> None:
        self.llm_service = llm_service
        self.vector_service = vector_service
        self.task_service = task_service

    async def index_chunks(
        self,
        *,
        db: AsyncSession,
        document: Document,
        version: DocumentVersion,
        kb_id: int,
        filename: str,
        chunks: list[str],
        state: DocumentProcessingState,
    ) -> None:
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
                token_count=None,
                metadata_={
                    "file_sha256": document.sha256,
                    "source_file_name": filename,
                },
            )
            db.add(document_chunk)
            await db.flush()

            state.stage = "embedding"
            embedding = await self.llm_service.embed_text(chunk)
            if not embedding:
                raise RuntimeError(
                    "Embedding result is empty: "
                    f"chunk_id={document_chunk.id}, chunk_no={index}"
                )
            if not all(
                isinstance(value, (int, float)) for value in embedding
            ):
                raise RuntimeError(
                    "Embedding contains invalid values: "
                    f"chunk_id={document_chunk.id}"
                )

            vector_id = str(document_chunk.id)
            state.stage = "vector_upserting"
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
            state.inserted_vector_ids.append(vector_id)

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

            state.processed_chunks += 1
            should_update_progress = (
                state.processed_chunks % 5 == 0
                or state.processed_chunks == state.total_chunks
            )
            if should_update_progress:
                vector_progress = 60 + int(
                    state.processed_chunks
                    / max(state.total_chunks, 1)
                    * 30
                )
                await self.task_service.update_progress(
                    state.task_id,
                    stage="vector_upserting",
                    progress=min(vector_progress, 90),
                    total_chunks=state.total_chunks,
                    processed_chunks=state.processed_chunks,
                    failed_chunks=0,
                )
