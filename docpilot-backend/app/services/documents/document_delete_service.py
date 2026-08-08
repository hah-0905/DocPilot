from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk_embeddings import ChunkEmbedding
from app.models.documents import Document, DocumentChunk, DocumentVersion
from app.services.documents.document_query_service import DocumentQueryService
from app.services.vector_service import VectorService


class DocumentDeleteService:
    """Coordinate vector deletion and relational soft deletion."""

    def __init__(
        self,
        *,
        query_service: DocumentQueryService,
        vector_service: VectorService,
    ) -> None:
        self.query_service = query_service
        self.vector_service = vector_service

    async def delete_document(
        self,
        db: AsyncSession,
        user_id: int,
        kb_id: int,
        document_id: int,
    ) -> bool:
        await self.query_service.get_owned_knowledge_base(
            db,
            user_id,
            kb_id,
        )

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
            ).values(enabled=False)
        )
        await db.execute(
            update(DocumentVersion).where(
                DocumentVersion.document_id == document_id,
            ).values(status="deleted")
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
