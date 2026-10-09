"""Model routing and legacy settings compatibility without network calls."""

import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call, patch

from app.core.config import Settings
from app.services.llm_service import LLMService


BASE_ENV = {
    "OPENAI_API_KEY": "chat-key",
    "OPENAI_BASE_URL": "http://llm.example:8001/v1",
    "MODEL_NAME": "chat-model",
    "EMBEDDING_MODEL": "embedding-model",
    "DATABASE_URL": "sqlite://",
    "OSS_ACCESS_KEY_ID": "test",
    "OSS_ACCESS_KEY_SECRET": "test",
    "OSS_ENDPOINT": "test",
    "OSS_BUCKET_NAME": "test",
}


def make_settings(**embedding_env: str) -> Settings:
    # Ignore local credentials and .env files so tests are deployment-independent.
    with patch.dict(os.environ, {**BASE_ENV, **embedding_env}, clear=True):
        return Settings(_env_file=None)


class LLMServiceConfigurationTests(unittest.TestCase):
    def test_embedding_overrides_and_fallbacks_are_independent(self):
        for base_url in (None, "", "http://embedding.example:8002/v1"):
            for api_key in (None, "", "embedding-key"):
                with self.subTest(base_url=base_url, api_key=api_key):
                    env = {}
                    if base_url is not None:
                        env["EMBEDDING_BASE_URL"] = base_url
                    if api_key is not None:
                        env["EMBEDDING_API_KEY"] = api_key
                    settings = make_settings(**env)
                    self.assertEqual(settings.embedding_base_url, base_url)
                    self.assertEqual(settings.embedding_api_key, api_key)

                    with (
                        patch("app.services.llm_service.get_settings", return_value=settings),
                        patch("app.services.llm_service.AsyncOpenAI") as constructor,
                    ):
                        LLMService()

                    self.assertEqual(constructor.call_args_list, [
                        call(api_key="chat-key", base_url=BASE_ENV["OPENAI_BASE_URL"]),
                        call(
                            api_key=api_key or "chat-key",
                            base_url=base_url or BASE_ENV["OPENAI_BASE_URL"],
                        ),
                    ])


class LLMServiceRoutingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        settings = make_settings(
            EMBEDDING_BASE_URL="http://embedding.example:8002/v1",
            EMBEDDING_API_KEY="embedding-key",
        )
        self.chat_client = MagicMock()
        self.embedding_client = MagicMock()
        for client in (self.chat_client, self.embedding_client):
            client.chat.completions.create = AsyncMock()
            client.embeddings.create = AsyncMock()

        with (
            patch("app.services.llm_service.get_settings", return_value=settings),
            patch(
                "app.services.llm_service.AsyncOpenAI",
                side_effect=[self.chat_client, self.embedding_client],
            ) as constructor,
        ):
            self.service = LLMService()
        self.assertEqual(constructor.call_args_list, [
            call(api_key="chat-key", base_url=BASE_ENV["OPENAI_BASE_URL"]),
            call(api_key="embedding-key", base_url=settings.embedding_base_url),
        ])
        self.assertIs(self.service.chat_client, self.chat_client)
        self.assertIs(self.service.embedding_client, self.embedding_client)
        self.messages = [{"role": "user", "content": "hello"}]

    async def test_chat_uses_chat_client(self):
        self.chat_client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="answer"))],
        )

        self.assertEqual(await self.service.chat(self.messages), "answer")

        self.chat_client.chat.completions.create.assert_awaited_once_with(
            model="chat-model", messages=self.messages,
            temperature=0.7, max_tokens=4096,
        )
        self.embedding_client.chat.completions.create.assert_not_called()

    async def test_stream_chat_uses_chat_client(self):
        async def chunks():
            yield SimpleNamespace(choices=[])
            for content in (None, "", "hello", " world"):
                yield SimpleNamespace(
                    choices=[SimpleNamespace(delta=SimpleNamespace(content=content))],
                )

        self.chat_client.chat.completions.create.return_value = chunks()

        result = [chunk async for chunk in self.service.stream_chat(
            self.messages, model="override-model", temperature=0.2, max_tokens=128,
        )]

        self.assertEqual(result, ["hello", " world"])
        self.chat_client.chat.completions.create.assert_awaited_once_with(
            model="override-model", messages=self.messages,
            temperature=0.2, max_tokens=128, stream=True,
        )
        self.embedding_client.chat.completions.create.assert_not_called()

    async def test_embed_text_uses_embedding_client(self):
        embedding = [0.5] * 1024
        self.embedding_client.embeddings.create.return_value = SimpleNamespace(
            data=[SimpleNamespace(embedding=embedding)],
        )

        self.assertEqual(await self.service.embed_text("document"), embedding)

        self.embedding_client.embeddings.create.assert_awaited_once_with(
            model="embedding-model", input="document",
        )
        self.chat_client.embeddings.create.assert_not_called()
