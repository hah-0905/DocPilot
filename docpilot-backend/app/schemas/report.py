from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class ReportTaskCreate(BaseModel):
    workspace_id: int

    kb_id: int
    title: str = Field(..., min_length=1, max_length=255)
    report_type: str = "technical_review"
    length: Literal["short", "medium", "long"] = "medium"
    citation_format: Literal["markdown", "plain"] = "markdown"
    instruction: Optional[str] = None
    model_name: Optional[str] = None


class ReportTaskResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )

    task_id: int = Field(validation_alias="id")
    title: str
    status: str
    result_content: str | None = None


class ReportExportCreate(BaseModel):
    export_format: Literal["markdown"] = "markdown"


class ReportExportResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )

    export_id: int = Field(validation_alias="id")
    task_id: int
    export_format: str
    file_name: str | None = None
    size_bytes: int | None = None
    status: str
    created_at: datetime
