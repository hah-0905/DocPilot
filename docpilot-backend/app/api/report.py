from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.report import ReportTaskCreate, ReportTaskResponse
from app.services.reports.report_services import ReportService


router = APIRouter(
    prefix="/api/report",
    tags=["报告相关接口"],
)

report_service = ReportService()


@router.post("/tasks", response_model=ReportTaskResponse)
async def create_report_task(
    request: ReportTaskCreate,
    db: AsyncSession = Depends(get_db),
):
    try:
        task = await report_service.create_report_task(
            db=db,
            request=request,
        )

        sections_config = await report_service.build_default_sections(
            report_type=request.report_type,
            length=request.length,
        )

        markdown_parts = [f"# {request.title}"]

        for section_config in sections_config:
            section_content = (
                f"本章节将围绕“{section_config['requirement']}”展开。"
                f"后续将接入知识库检索、chunk 引用和大模型生成逻辑。"
            )

            await report_service.create_report_section(
                db=db,
                task_id=task.id,
                section=section_config,
                section_content=section_content,
            )

            markdown_parts.append(
                f"## {section_config['order_no']}. "
                f"{section_config['title']}\n\n"
                f"{section_content}"
            )

        final_markdown = "\n\n".join(markdown_parts)

        task.result_content = final_markdown
        task.status = "success"
        task.finished_at = datetime.utcnow()
        task.config = {
            **(task.config or {}),
            "progress": 100,
        }

        await db.commit()
        await db.refresh(task)

        return ReportTaskResponse(
            task_id=task.id,
            title=task.title,
            status=task.status,
            result_content=task.result_content,
        )

    except HTTPException:
        await db.rollback()
        raise

    except Exception as exc:
        await db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"报告任务创建失败：{exc}",
        ) from exc