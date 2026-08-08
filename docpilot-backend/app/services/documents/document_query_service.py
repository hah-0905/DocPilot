from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models.documents import Document, DocumentChunk, DocumentVersion
from app.models.kb import KnowledgeBase
from app.models.workspaces import Workspace


class DocumentQueryService:
    """Read document data and enforce knowledge-base ownership."""

    async def get_owned_knowledge_base(
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

    async def list_documents(
        self,
        db: AsyncSession,
        user_id: int,
        kb_id: int,
    ) -> list[Document]:
        kb = await self.get_owned_knowledge_base(db, user_id, kb_id)

        result = await db.execute(
            select(Document).where(
                Document.kb_id == kb.id,
                Document.deleted_at.is_(None),
                Document.enabled == True,
            ).order_by(Document.created_at.desc())
        )
        return result.scalars().all()

    async def count_chunks(
        self,
        db: AsyncSession,
        document_id: int,
        kb_id: int,
    ) -> int:
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

    async def get_document_version(
        self,
        db: AsyncSession,
        kb_id: int,
        document_id: int,
    ) -> DocumentVersion | None:
        result = await db.execute(
            select(DocumentVersion).join(
                Document,
                DocumentVersion.document_id == Document.id,
            ).where(
                Document.id == document_id,
                Document.kb_id == kb_id,
                Document.deleted_at.is_(None),
                Document.enabled == True,
            ).order_by(DocumentVersion.version_no.desc())
        )
        return result.scalar_one_or_none()

    async def get_document(
        self,
        db: AsyncSession,
        user_id: int,
        kb_id: int,
        document_id: int,
    ) -> Document | None:
        await self.get_owned_knowledge_base(db, user_id, kb_id)

        document = await db.execute(
            select(Document).where(
                Document.id == document_id,
                Document.kb_id == kb_id,
                Document.deleted_at.is_(None),
                Document.enabled == True,
            )
        )
        return document.scalar_one_or_none()
