from pydantic import BaseModel, Field

class ChatCompletionRequest(BaseModel):
    session_id: str = Field(..., min_length=1, description="会话 ID")
    message: str = Field(..., min_length=1, description="用户输入的消息")
    stream: bool = Field(default=False, description="是否流式返回结果")

