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
        document = await self.query_service.get_document(
            db, user_id=user_id, kb_id=kb_id, document_id=document_id,
            for_update=True,
        )
        if document is None:
            return False

        # Use a locking/current read: an indexing transaction may have completed
        # while we waited for the document lock, after this transaction's snapshot.
        result = await db.execute(
            select(ChunkEmbedding.vector_id).join(
                DocumentChunk, ChunkEmbedding.chunk_id == DocumentChunk.id,
            ).where(
                ChunkEmbedding.kb_id == kb_id,
                DocumentChunk.document_id == document.id,
                DocumentChunk.kb_id == kb_id,
            ).with_for_update()
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
                DocumentVersion.document_id.in_(
                    select(Document.id).where(Document.id == document_id, Document.kb_id == kb_id)
                ),
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
