from urllib.parse import urlsplit

from fastapi import HTTPException

from app.core.config import ModelProvider, get_settings


def platform_models() -> list[str]:
    settings = get_settings()
    return list(dict.fromkeys([settings.model_name, *settings.platform_models]))


def providers() -> dict[str, ModelProvider]:
    settings = get_settings()
    catalog = {"platform": ModelProvider(
        id="platform", label="平台服务商", base_url=settings.openai_base_url,
        models=platform_models(),
    )}
    for provider in settings.personal_model_providers:
        try:
            url = urlsplit(provider.base_url)
        except ValueError:
            raise HTTPException(503, "个人模型服务商目录配置无效，请联系管理员") from None
        if (provider.id in catalog or url.scheme != "https" or not url.hostname
                or url.username or url.password or url.query or url.fragment
                or any(not m or len(m) > 128 for m in provider.models)):
            raise HTTPException(503, "个人模型服务商目录配置无效，请联系管理员")
        catalog[provider.id] = provider
    return catalog


def validate_model(provider_id: str, model_name: str) -> ModelProvider:
    provider = providers().get(provider_id)
    if provider is None or model_name not in provider.models:
        # Never echo untrusted strings; they may contain credentials.
        raise HTTPException(422, "所选服务商或模型不受支持，请重新选择")
    return provider
