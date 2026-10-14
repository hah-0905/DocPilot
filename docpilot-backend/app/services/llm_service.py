from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress
from typing import Any, TYPE_CHECKING

from fastapi import HTTPException
from openai import AsyncOpenAI, APITimeoutError, AuthenticationError

from app.core.config import get_settings
if TYPE_CHECKING:
    from app.services.model_runtime import ModelRuntime


class LLMService:
    """Each operation owns its client; no mutable shared user credentials."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.default_model = self.settings.model_name
        self.embedding_model = self.settings.embedding_model

    @asynccontextmanager
    async def _client(self, *, runtime=None, embedding=False, timeout=None):
        settings = self.settings
        if embedding:
            key = settings.embedding_api_key or settings.openai_api_key
            url = settings.embedding_base_url or settings.openai_base_url
        else:
            key = runtime.api_key if runtime else settings.openai_api_key
            url = runtime.base_url if runtime else settings.openai_base_url
        client = None
        try:
            client = AsyncOpenAI(
                api_key=key, base_url=url,
                timeout=timeout or settings.llm_timeout_seconds, max_retries=0,
            )
            yield client
        except (APITimeoutError, TimeoutError):
            raise HTTPException(504, "模型服务请求超时，请稍后重试") from None
        except AuthenticationError:
            raise HTTPException(502, "模型服务认证失败，请检查所选模型来源的 API Key") from None
        except HTTPException:
            raise
        except Exception:
            # Provider errors can echo request headers and credentials.
            raise HTTPException(502, "模型服务调用失败，请检查凭据、模型和服务商状态") from None
        finally:
            if client is not None:
                with suppress(Exception):
                    await client.close()

    async def chat(
        self, messages: list[dict[str, Any]], model: str | None = None,
        temperature: float = 0.7, max_tokens: int = 4096,
        *, runtime: ModelRuntime | None = None, timeout: float | None = None,
    ) -> str:
        async with self._client(runtime=runtime, timeout=timeout) as client:
            response = await client.chat.completions.create(
                model=runtime.model_key if runtime else model or self.default_model,
                messages=messages,
                temperature=runtime.temperature if runtime else temperature,
                max_tokens=runtime.max_tokens if runtime else max_tokens,
            )
            return response.choices[0].message.content or ""

    async def stream_chat(
        self, messages: list[dict[str, Any]], model: str | None = None,
        temperature: float = 0.7, max_tokens: int = 4096,
        *, runtime: ModelRuntime | None = None,
    ) -> AsyncGenerator[str, None]:
        async with self._client(runtime=runtime) as client:
            stream = await client.chat.completions.create(
                model=runtime.model_key if runtime else model or self.default_model,
                messages=messages,
                temperature=runtime.temperature if runtime else temperature,
                max_tokens=runtime.max_tokens if runtime else max_tokens, stream=True,
            )
            try:
                async for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
            finally:
                await stream.close()

    async def embed_text(self, text: str) -> list[float]:
        async with self._client(embedding=True) as client:
            response = await client.embeddings.create(model=self.embedding_model, input=text)
            return response.data[0].embedding
