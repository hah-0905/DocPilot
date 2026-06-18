from datetime import datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report import ReportSection, ReportTask
from app.schemas.report import ReportTaskCreate
from app.services.rag_service import RagService
from app.services.llm_service import LLMService


class ReportService:

    def __init__(self) -> None:
        self.rag_service = RagService()
        self.llm_service = LLMService()

    async def create_report_task(
        self,
        db: AsyncSession,
        request: ReportTaskCreate,
        user_id: int,
    ) -> ReportTask:
        """创建报告任务。"""

        task = ReportTask(
            title=request.title,
            user_id=user_id,
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
        """创建报告章节。"""

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
                    {"order_no": 1, "title": "背景", "requirement": "概述主题背景和研究意义"},
                    {"order_no": 2, "title": "核心内容", "requirement": "总结核心流程和关键技术"},
                    {"order_no": 3, "title": "总结", "requirement": "总结技术价值和后续方向"},
                ]

            return [
                {"order_no": 1, "title": "背景", "requirement": "说明该技术的背景、问题来源和研究意义"},
                {"order_no": 2, "title": "核心流程", "requirement": "说明该技术的主要流程、关键步骤和整体架构"},
                {"order_no": 3, "title": "关键技术", "requirement": "总结相关关键技术、方法路线和系统组成"},
                {"order_no": 4, "title": "应用价值", "requirement": "说明该技术的落地价值、优势和限制"},
            ]

        return [
            {"order_no": 1, "title": "概述", "requirement": "对报告主题进行总体介绍"},
            {"order_no": 2, "title": "主要内容", "requirement": "围绕报告主题展开核心内容"},
            {"order_no": 3, "title": "总结", "requirement": "总结主要结论和后续方向"},
        ]

    async def retrieve_section_chunks(
        self,
        db: AsyncSession,
        kb_id: int,
        task: ReportTask,
        section_title: str,
        section_requirement: str,
        top_k: int,
    ) -> list[dict]:
        query_parts = [
            f"报告主题：{task.title}",
            f"报告类型：{task.report_type}",
            f"报告总要求：{task.instruction or ''}",
            f"章节标题：{section_title}",
            f"章节要求：{section_requirement}",
        ]

        query = "\n".join(query_parts)

        return await self.rag_service.search(
            db=db,
            kb_id=kb_id,
            query=query,
            top_k=top_k,
        )

    async def generate_section_content(
        self,
        db: AsyncSession,
        task: ReportTask,
        section_config: dict[str, Any],
        chunks: list[dict],
    ) -> str:
        """使用 LLM 生成章节内容。"""

        if not chunks:
            return (
                f"本章节围绕“{section_config.get('requirement', '')}”展开。"
                f"当前知识库中未检索到相关引用内容。"
            )

        context = "\n\n".join(
            f"[{index + 1}] {chunk['content'][:500]}"
            for index, chunk in enumerate(chunks)
        )

        messages = [
            {
                "role": "system",
                "content": (
                    "你是一个专业报告撰写助手。请根据用户提供的报告主题、章节要求"
                    "以及知识库检索结果，撰写该章节内容。"
                    "要求：内容详实、逻辑清晰、引用检索结果中的具体信息。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"报告主题：{task.title}\n"
                    f"报告类型：{task.report_type}\n"
                    f"章节标题：{section_config['title']}\n"
                    f"章节要求：{section_config.get('requirement', '')}\n"
                    f"补充要求：{task.instruction or '无'}\n\n"
                    f"以下是从知识库中检索到的参考资料：\n\n{context}\n\n"
                    f"请基于上述参考资料撰写该章节，在文中适当位置标注引用编号。"
                ),
            },
        ]

        try:
            content = await self.llm_service.chat(messages)
            return content or (
                f"本章节围绕“{section_config.get('requirement', '')}”展开。"
            )
        except Exception:
            return (
                f"本章节围绕“{section_config.get('requirement', '')}”展开。"
                f"LLM 生成暂不可用，以下为检索到的参考内容：\n\n{context[:1000]}"
            )

    async def get_report_tasks(
            self,
            db: AsyncSession,
            user_id: int,
            status: str = "success",
    ) -> list[ReportTask]:
        """获取报告任务列表。"""
        result = await db.execute(
            select(ReportTask)
            .where(ReportTask.user_id == user_id)
            .where(ReportTask.status == status)
        )

        return result.scalars().all()
    

    async def get_report_task_detail(
            self,
            db: AsyncSession,
            task_id: int,
            user_id: int,
    ) -> ReportTask:
        """获取报告任务详情。"""
        result = await db.execute(
            select(ReportTask)
            .where(ReportTask.id == task_id,
                   ReportTask.user_id == user_id,
                   ReportTask.status == "success")
        )

        return result.scalars().first()
    

    async def delete_report_task(
            self,
            db: AsyncSession,
            task_id: int,
            user_id: int,
    )-> None:
        '''
        删除报告任务
        '''
        task = await db.execute(
            select(ReportTask)
            .where(ReportTask.id == task_id)
            .where(ReportTask.user_id == user_id)
        )
        if not task:
            return False
        await db.execute(
            delete(ReportSection)
            .where(ReportSection.task_id == task_id)
        )
        await db.execute(
            delete(ReportSection)
            .where(ReportSection.task_id == task_id)
        )
        await db.execute(
            delete(ReportTask)
            .where(ReportTask.user_id == user_id)
        )
        await db.commit()
        return True
    