"""Shared document lock and version checks for background writers."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.documents import Document, DocumentVersion


class DocumentUnavailable(Exception):
    """The document was removed, disabled, or superseded."""


async def lock_current_document(
    db: AsyncSession,
    document_id: int,
    version_id: int,
    *,
    kb_id: int | None = None,
) -> tuple[Document, DocumentVersion]:
    # Always lock the document first, just as deletion does. Fresh locking reads
    # avoid both the ORM identity cache and stale MySQL repeatable-read snapshots.
    document = await db.get(
        Document, document_id, with_for_update=True, populate_existing=True,
    )
    if (
        document is None or not document.enabled or document.deleted_at is not None
        or document.current_version_id != version_id
        or (kb_id is not None and document.kb_id != kb_id)
    ):
        raise DocumentUnavailable("文档已删除、停用、更新或不属于该知识库")
    version = await db.get(
        DocumentVersion, version_id, with_for_update=True, populate_existing=True,
    )
    if version is None or version.document_id != document.id or version.status == "deleted":
        raise DocumentUnavailable("文档版本已失效")
    return document, version
