from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report import ReportSection, ReportTask
from app.schemas.report import ReportTaskCreate


class ReportService:

    async def create_report_task(
        self,
        db: AsyncSession,
        request: ReportTaskCreate,
    ) -> ReportTask:
        """创建报告任务。"""

        task = ReportTask(
            title=request.title,
            user_id=request.user_id,
            workspace_id=request.workspace_id,
            report_type=request.report_type,
            instruction=request.instruction,
            model_name=request.model_name,
            status="running",
            started_at=datetime.utcnow(),
            config={
                "kb_id": request.kb_id,
                "length": request.length,
                "citation_format": request.citation_format,
                "progress": 0,
            },
        )

        db.add(task)
        await db.flush()

        return task

    async def create_report_section(
        self,
        db: AsyncSession,
        task_id: int,
        section: dict[str, Any],
        section_content: str,
    ) -> ReportSection:
        """创建报告章节，但不在这里提交事务。"""

        report_section = ReportSection(
            task_id=task_id,
            order_no=section["order_no"],
            title=section["title"],
            requirement=section.get("requirement"),
            content=section_content,
            status="success",
        )

        db.add(report_section)
        await db.flush()

        return report_section

    async def build_default_sections(
        self,
        report_type: str,
        length: str,
    ) -> list[dict[str, Any]]:
        if report_type == "technical_review":
            if length == "short":
                return [
                    {
                        "order_no": 1,
                        "title": "背景",
                        "requirement": "概述主题背景和研究意义",
                    },
                    {
                        "order_no": 2,
                        "title": "核心内容",
                        "requirement": "总结核心流程和关键技术",
                    },
                    {
                        "order_no": 3,
                        "title": "总结",
                        "requirement": "总结技术价值和后续方向",
                    },
                ]

            return [
                {
                    "order_no": 1,
                    "title": "背景",
                    "requirement": "说明该技术的背景、问题来源和研究意义",
                },
                {
                    "order_no": 2,
                    "title": "核心流程",
                    "requirement": "说明该技术的主要流程、关键步骤和整体架构",
                },
                {
                    "order_no": 3,
                    "title": "关键技术",
                    "requirement": "总结相关关键技术、方法路线和系统组成",
                },
                {
                    "order_no": 4,
                    "title": "应用价值",
                    "requirement": "说明该技术的落地价值、优势和限制",
                },
            ]

        return [
            {
                "order_no": 1,
                "title": "概述",
                "requirement": "对报告主题进行总体介绍",
            },
            {
                "order_no": 2,
                "title": "主要内容",
                "requirement": "围绕报告主题展开核心内容",
            },
            {
                "order_no": 3,
                "title": "总结",
                "requirement": "总结主要结论和后续方向",
            },
        ]