from pydantic import BaseModel, ConfigDict, Field, model_validator


class ModelSettingsUpdate(BaseModel):
    """Fields that can be changed for a workspace's model settings."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    model_key: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        description="模型内部标识，例如 deepseek-chat 或 gpt-4o-mini",
    )
    temperature: float | None = Field(
        default=None,
        ge=0,
        le=2,
        description="采样温度，范围为 0 到 2",
    )
    max_tokens: int | None = Field(
        default=None,
        ge=1,
        le=1_000_000,
        description="最大生成 Token 数，具体上限还应由服务层按模型校验",
    )
    response_language: str | None = Field(
        default=None,
        min_length=2,
        max_length=32,
        description="默认回复语言，例如 zh-CN、en-US 或 auto",
    )

    @model_validator(mode="after")
    def ensure_at_least_one_field(self):
        if not self.model_fields_set:
            raise ValueError("至少提供一个需要更新的模型设置字段")
        return self
