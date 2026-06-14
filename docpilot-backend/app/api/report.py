import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from fastapi import APIRouter, Depends, HTTPException
from app.schemas.report import ReportTaskCreate, ReportTaskResponse
from app.services.reports.report_services import ReportService


router = APIRouter(prefix="/api/report", tags=["报告相关接口"])

report_service = ReportService()


@router.post("/tasks")
async def create_report_task(
    request: ReportTaskCreate,
    db: AsyncSession = Depends(get_db)
):

    task = await report_service.create_report_task(db, request)

    sections_config = await report_service.build_default_sections(
        request.report_type,
        request.length
    )

    markdown_parts = [f"#{request.title}\n"]

    for section in sections_config:
        section_content = {
            f"本章节将围绕“{section['requirement']}”展开。"
            f"后续将接入知识库检索、chunk 引用和大模型生成逻辑。"
        }

        section = await report_service.create_report_section(db, section, section_content)

        markdown_parts.append(
            f"## {section['order_no']}. {section['title']}\n\n"
            f"{section_content}\n"
        )

        final_markdown = "\n".join(markdown_parts)

        task.result_content = final_markdown
        task.status = "success"
        task.finished_at = datetime.utcnow()
        task.config = {
            **(task.config or {}),
            "progress": 100,
        }

        try:
            await db.commit()
            await db.refresh(task)
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"报告任务创建失败：{str(e)}")

        return ReportTaskResponse(
            task_id=task.id,
            title=task.title,
            status=task.status,
            result_content=task.result_content,
        )
