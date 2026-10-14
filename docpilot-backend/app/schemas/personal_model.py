from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class PersonalModelUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: str = Field(min_length=1, max_length=32, pattern=r"^[a-z][a-z0-9_-]*$")
    model_name: str = Field(min_length=1, max_length=128)
    api_key: SecretStr | None = None
    enabled: bool = True

    @field_validator("api_key")
    @classmethod
    def validate_key(cls, value):
        if value is not None:
            key = value.get_secret_value()
            if not 8 <= len(key) <= 4096 or any(ord(c) < 33 or ord(c) > 126 for c in key):
                raise ValueError("API Key 格式无效")
        return value


class PersonalModelStatus(BaseModel):
    available: bool
    configured: bool
    enabled: bool = False
    provider_id: str | None = None
    model_name: str | None = None
    key_mask: str | None = None
    unavailable_reason: str | None = None
