from collections.abc import AsyncGenerator
from typing import Any

from app.core.config import get_settings
from openai import AsyncOpenAI


class LLMService:

    def __init__(self) -> None:
        settings = get_settings()

        self.client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url
        )
        self.default_model = settings.model_name
        self.embedding_model = settings.embedding_model

    async def chat(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        '''
        聊天
        '''
        response = await self.client.chat.completions.create(
            model=model or self.default_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = response.choices[0].message.content
        return content or ""

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        '''
        流式聊天
        '''
        stream = await self.client.chat.completions.create(
            model=model or self.default_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        async for chunk in stream:
            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta
            content = delta.content

            if content:
                yield content

    async def embed_text(
        self,
        text: str
    ) -> list[float]:
        '''
        嵌入文本
        '''
        response = await self.client.embeddings.create(
            model=self.embedding_model,
            input=text,
        )

        return response.data[0].embedding
