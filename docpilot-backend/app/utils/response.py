from typing import Any

from pydantic import BaseModel

class ApiResponse(BaseModel):
    code: int = 200
    message: str = "success"
    data: Any = None
