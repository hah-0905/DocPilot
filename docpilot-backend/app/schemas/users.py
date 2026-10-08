from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator, model_validator


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
    username: str | None = None
    email: EmailStr | None = None
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

class UserInfoUpdate(BaseModel):
    """Partial profile update; credentials cannot be changed here."""

    model_config = ConfigDict(extra="forbid")

    username: str | None = Field(default=None, min_length=3, max_length=64)
    email: EmailStr | None = None
    display_name: str | None = Field(default=None, max_length=128)

    @model_validator(mode="after")
    def validate_update(self):
        if not self.model_fields_set:
            raise ValueError("至少提供一个资料字段")
        for name in ("username", "email"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} 不能为 null")
        return self


class PasswordChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def reject_bcrypt_truncation(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("新密码的 UTF-8 编码不能超过 72 字节")
        return value
