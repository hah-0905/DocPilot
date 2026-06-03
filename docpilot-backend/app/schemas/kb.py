
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CreateKnowledgeBaseRequest(BaseModel):
    name: str = Field(..., min_length=1)
    description: str | None = None
    workspace_id: int = Field(..., gt=0)


class UpdateKnowledgeBaseRequest(BaseModel):
    name: str | None = Field(None, min_length=1)
    description: str | None = None
    visibility: str | None = None
    embedding_model: str | None = None
    rerank_model: str | None = None
    chunk_strategy: str | None = None
    chunk_size: int | None = Field(None, gt=0)
    chunk_overlap: int | None = Field(None, ge=0)
    default_top_k: int | None = Field(None, ge=1, le=20)


class KnowledgeBaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    name: str
    description: str | None = None
    visibility: str
    status: str
    created_by: int
    created_at: datetime
    updated_at: datetime


class RagSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


class RagChatRequest(BaseModel):
    kb_id: int = Field(..., min_length=1)
    question: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
