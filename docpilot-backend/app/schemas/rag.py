from pydantic import BaseModel, Field

class CreateKnowledgeBaseRequest(BaseModel):
    name: str = Field(..., min_length=1)
    description: str | None = None


class RagSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


class RagChatRequest(BaseModel):
    kb_id: str = Field(..., min_length=1)
    question: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)