from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import get_settings
from app.models.workspace_model_settings import WorkspaceModelSettings
from app.models.workspace_retrieval_settings import WorkspaceRetrievalSettings
from app.models.workspace_report_settings import WorkspaceReportSettings
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class ModelRuntimeSettings:
    model_key: str
    temperature: float
    max_tokens: int
    response_language: str


class WorkspaceSettingsService:

    async def get_model_settings(
        self,
        db: AsyncSession,
        workspace_id: int,
    ) -> ModelRuntimeSettings:
        result = await db.execute(
            select(WorkspaceModelSettings).where(
                WorkspaceModelSettings.workspace_id == workspace_id
            )
        )
        row = result.scalar_one_or_none()

        if row is None:
            app_settings = get_settings()

            return ModelRuntimeSettings(
                model_key=app_settings.model_name,
                temperature=0.7,
                max_tokens=4096,
                response_language="zh-CN",
            )

        return ModelRuntimeSettings(
            model_key=row.model_key,
            temperature=float(row.temperature),
            max_tokens=row.max_tokens,
            response_language=row.response_language,
        )

    async def get_retrieval_settings(
        self,
        db: AsyncSession,
        workspace_id: int,
    ) -> WorkspaceRetrievalSettings | None:
        result = await db.execute(
            select(WorkspaceRetrievalSettings).where(
                WorkspaceRetrievalSettings.workspace_id == workspace_id
            )
        )
        return result.scalar_one_or_none()

    async def get_report_settings(
        self,
        db: AsyncSession,
        workspace_id: int,
    ) -> WorkspaceReportSettings | None:
        result = await db.execute(
            select(WorkspaceReportSettings).where(
                WorkspaceReportSettings.workspace_id == workspace_id
            )
        )
        return result.scalar_one_or_none()


workspace_settings_service = WorkspaceSettingsService()
