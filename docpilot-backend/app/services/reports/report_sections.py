from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report import ReportSection


class ReportSectionsService:
    async def create_report_section(
        self,
        db: AsyncSession,
        task_id: int,
        section: dict[str, Any],
        section_content: str,
        parent_section_id: int,
    ) -> ReportSection:
        report_section = ReportSection(
            task_id=task_id,
            order_no=section["order_no"],
            title=section["title"],
            requirement=section.get("requirement"),
            content=section_content,
            status="success",
            parent_section_id=parent_section_id
        )

        db.add(report_section)
        await db.flush()
        return report_section
