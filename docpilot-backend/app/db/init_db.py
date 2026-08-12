from app.db.base import Base
from app.db.session import async_engine

# 必须导入，使模型注册到 Base.metadata。
from app.models.workspaces import Workspace  # noqa: F401
from app.models.workspace_model_settings import WorkspaceModelSettings  # noqa: F401
from app.models.workspace_report_settings import WorkspaceReportSettings  # noqa: F401
from app.models.workspace_retrieval_settings import (  # noqa: F401
    WorkspaceRetrievalSettings,
)
from app.models.document_processing_tasks import (  # noqa: F401
    DocumentProcessingTask,
)

async def init_db() -> None:
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
