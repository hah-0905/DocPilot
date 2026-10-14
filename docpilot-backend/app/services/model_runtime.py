from dataclasses import dataclass, field

from fastapi import HTTPException

from app.core.config import get_settings
from app.services.model_catalog import platform_models, validate_model
from app.services.personal_model_service import decrypt_key, personal_model_service
from app.services.workspace_settings_service import workspace_settings_service


@dataclass(frozen=True, slots=True)
class ModelRuntime:
    model_key: str
    api_key: str = field(repr=False)
    base_url: str
    source: str
    temperature: float = 0.7
    max_tokens: int = 4096
    response_language: str = "zh-CN"


async def resolve_model_runtime(db, user_id: int, workspace_id: int) -> ModelRuntime:
    workspace = await workspace_settings_service.get_model_settings(db, workspace_id)
    personal = await personal_model_service.get_row(db, user_id)
    if personal is not None and personal.enabled:
        provider = validate_model(personal.provider_id, personal.model_name)
        return ModelRuntime(
            model_key=personal.model_name, api_key=decrypt_key(personal),
            base_url=provider.base_url, source="personal", temperature=workspace.temperature,
            max_tokens=workspace.max_tokens, response_language=workspace.response_language,
        )
    settings = get_settings()
    if workspace.model_key not in platform_models():
        raise HTTPException(422, "工作区模型已不受平台支持，请在设置页重新选择模型")
    return ModelRuntime(
        model_key=workspace.model_key, api_key=settings.openai_api_key,
        base_url=settings.openai_base_url, source="platform", temperature=workspace.temperature,
        max_tokens=workspace.max_tokens, response_language=workspace.response_language,
    )
