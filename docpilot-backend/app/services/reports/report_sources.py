from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.report import ReportSource


class ReportSourceService:
    async def save_report_sources(
        self,
        db: AsyncSession,
        task_id: int,
        section_id: int,
        kb_id: int,
        chunks: list[dict],
    ) -> list[ReportSource]:
        sources = []

        for citation_no, chunk in enumerate(chunks, start=1):
            score = chunk.get("score")

            source = ReportSource(
                task_id=task_id,
                section_id=section_id,
                kb_id=kb_id,
                document_id=int(chunk["document_id"]),
                chunk_id=chunk["chunk_id"],
                score=Decimal(str(score)) if score else None,
                citation_no=citation_no,
                quote_text=chunk.get("content"),
            )

            db.add(source)
            sources.append(source)

        await db.flush()
        return sources
