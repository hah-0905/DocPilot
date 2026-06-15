from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.utils.response import ApiResponse
from app.db.session import get_db
from app.models.report import ReportSource
from app.models.users import User
from app.schemas.report import ReportTaskCreate, ReportTaskResponse
from app.services.reports.report_services import ReportService
from app.services.reports.report_sources import ReportSourceService
from app.services.users_service import get_current_user


router = APIRouter(
    prefix="/api/report",
    tags=["报告相关接口"],
)

report_service = ReportService()
report_sources_service = ReportSourceService()

@router.post("/tasks", response_model=ReportTaskResponse)
async def create_report_task(
    request: ReportTaskCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    '''
    创建报告任务
    '''
    try:
        task = await report_service.create_report_task(
            db=db,
            request=request,
            user_id=current_user.id,
        )

        sections_config = await report_service.build_default_sections(
            report_type=request.report_type,
            length=request.length,
        )

        markdown_parts = [f"# {request.title}"]

        for section_config in sections_config:
            query = "\n".join(
                part
                for part in [
                    f"报告主题：{task.title}",
                    f"报告总要求：{task.instruction or ''}",
                    f"章节标题：{section_config['title']}",
                    f"章节要求：{section_config.get('requirement') or ''}",
                ]
                if part
            )

            chunks = await report_service.retrieve_section_chunks(
                db=db, kb_id=request.kb_id, task=task,
                section_title=section_config["title"],
                section_requirement=section_config.get("requirement", ""),
                top_k=5,
            )

            section_content = await report_service.generate_section_content(
                db=db,
                task=task,
                section_config=section_config,
                chunks=chunks,
            )

            section = await report_service.create_report_section(
                db=db,
                task_id=task.id,
                section=section_config,
                section_content=section_content,
            )

            saved_sources = await report_sources_service.save_report_sources(
                db=db,
                task_id=task.id,
                section_id=section.id,
                kb_id=request.kb_id,
                chunks=chunks,
            )

            ref_lines = []
            for src in saved_sources:
                ref_lines.append(
                    f"  - [{src.citation_no}] 文档 #{src.document_id}，Chunk #{src.chunk_id}"
                    + (f"（相关度：{src.score}）" if src.score else "")
                )
            ref_block = "\n".join(ref_lines) if ref_lines else "  （暂无引用）"

            markdown_parts.append(
                f"## {section_config['order_no']}. "
                f"{section_config['title']}\n\n"
                f"{section_content}\n\n"
                f"**引用来源：**\n{ref_block}"
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
    
@router.get("/tasks")
async def get_report_tasks(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    '''
    获取报告任务列表
    '''
    task_list = await report_service.get_report_tasks(
        db=db,
        user_id=current_user.id,
    )


    return  ApiResponse(
        message="获取成功",
        data=[ReportTaskResponse.model_validate(task) for task in task_list]
        )

@router.get("/tasks/{task_id}")
async def get_report_task_detail(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    '''
    获取报告任务详情
    '''
    # 获取报告任务
    task = await report_service.get_report_task_detail(
        db=db,
        task_id=task_id,
        user_id=current_user.id,
    )
    # 检查报告任务是否存在
    if task is None:
        raise HTTPException(
            status_code=404,
            detail="报告任务不存在",
        )
    return  ApiResponse(
        message="获取成功",
        data=ReportTaskResponse.model_validate(task)
        )
