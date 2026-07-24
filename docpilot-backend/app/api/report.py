from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.utils.response import ApiResponse
from app.db.session import get_db
from app.models.report import ReportExport, ReportSection, ReportTask
from app.models.users import User
from app.schemas.report import ReportExportCreate, ReportExportResponse, ReportTaskCreate, ReportTaskResponse
from app.services.reports.report_services import ReportService
from app.services.users_service import get_current_user
from app.services.reports.report_sections import ReportSectionsService
from app.services.reports.report_sources import ReportSourcesService

from app.services.reports.report_exports import ReportExportService
from app.core.config import get_settings
from app.core.storage import path_in_directory


router = APIRouter(
    prefix="/api/report",
    tags=["报告相关接口"],
)

report_service = ReportService()
report_sources_service = ReportSourcesService()
report_sections_service = ReportSectionsService()
report_export_service = ReportExportService()


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

            section = await report_sections_service.create_report_section(
                db=db,
                task_id=task.id,
                section=section_config,
                section_content=section_content,
                parent_section_id=section_config.get("parent_section_id"),
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

    return ApiResponse(
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
    return ApiResponse(
        message="获取成功",
        data=ReportTaskResponse.model_validate(task)
    )


@router.delete("/tasks/{task_id}")
async def delete_report_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    '''
    删除报告任务
    '''
    deleted = await report_service.delete_report_task(
        db=db,
        task_id=task_id,
        user_id=current_user.id,
    )
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="报告任务不存在",
        )

    return ApiResponse(
        message="删除成功",
        deleted={
            "task_id": task_id,
            "deleted": True,
        }
    )


@router.post("/tasks/{task_id}/export")
async def create_report_export(
    task_id: int,
    request: ReportExportCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    创建报告导出
    """
    if request.export_format not in ["markdown",]:
        raise HTTPException(
            status_code=400,
            detail="目前只支持md文件导出",
        )

    export = await report_export_service.create_markdown_export(
        db=db,
        task_id=task_id,
        user_id=current_user.id,
    )

    return ApiResponse(
        message="导出文件已生成",
        data=ReportExportResponse.model_validate(export),
    )


@router.get("/exports/{export_id}/download")
async def download_report_export(
    export_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    下载报告导出
    """
    export = await report_export_service.get_export_for_download(
        db=db,
        export_id=export_id,
        user_id=current_user.id,
    )
    try:
        file_path = path_in_directory(
            Path(get_settings().export_dir),
            Path(export.storage_uri),
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="导出文件不存在") from None

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="导出文件不存在",
        )
    
    media_types = {
        "markdown": "text/markdown; charset=utf-8",
        "docx": (
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        ),
        "pdf": "application/pdf",
    }

    return FileResponse(
        path=file_path,
        filename=export.file_name or file_path.name,
        media_type=media_types.get(
            export.export_format,
            "application/octet-stream",
        ),
    )


@router.get("/tasks/{task_id}/exports")
async def list_report_exports(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    '''
    获取报告导出列表
    '''
    task_result = await db.execute(
        select(ReportTask)
        .where(ReportTask.id == task_id)
        .where(ReportTask.user_id == current_user.id)
    )
    task = task_result.scalar_one_or_none()

    if task is None:
        raise HTTPException(
            status_code=404,
            detail="报告任务不存在",
        )
    
    result = await db.execute(
        select(ReportExport)
        .where(ReportExport.task_id == task_id)
        .order_by(ReportExport.created_at.desc())
    )
    exports = result.scalars().all()

    return ApiResponse(
        message="获取成功",
        data=[
            ReportExportResponse.model_validate(export)
            for export in exports
        ]
    )
