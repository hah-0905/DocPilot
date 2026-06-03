from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UserInfoBase(BaseModel):
    """
    注册请求体
    前端传入的数据
    """

    username: str = Field(
        min_length=3,
        max_length=64,
        description="用户名，3-64位",
    )

    email: EmailStr = Field(
        description="邮箱地址",
    )

    password: str = Field(
        min_length=6,
        max_length=128,
        description="密码，至少6位",
    )

    display_name: Optional[str] = Field(
        default=None,
        max_length=128,
        description="显示名称",
    )


class UserInfoResponse(BaseModel):
    """
    用户信息响应体
    返回给前端的数据，不能包含 password_hash
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    status: str

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class UserAuthResponse(BaseModel):
    """
    注册 / 登录成功后的认证响应体
    """

    token: str
    user_info: UserInfoResponse

class UserLogin(BaseModel):
    """
    用户登录请求体
    前端传入的数据
    """

    username: Optional[str] = Field(
        default=None,
        min_length=3,
        max_length=64,
        description="用户名，3-64位",
    )

    email: Optional[EmailStr] = Field(
        default=None,
        description="邮箱地址",
    )

    password: str = Field(
        min_length=6,
        max_length=128,
        description="密码，至少6位",
    )