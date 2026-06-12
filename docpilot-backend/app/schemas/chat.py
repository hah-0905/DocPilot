from pydantic import BaseModel, Field


class ChatCompletionRequest(BaseModel):
    session_id: str | int | None = Field(default=None, description="Chat session ID")
    message: str = Field(..., min_length=1, description="User message")
    stream: bool = Field(default=False, description="Whether to stream the answer")
    kb_id: int | None = Field(default=None, description="Knowledge base ID")
