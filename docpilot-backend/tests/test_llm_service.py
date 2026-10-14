"""Real routing/lifecycle behavior with simulated SDK clients and no network."""
import asyncio
import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from fastapi import HTTPException
from openai import AuthenticationError, APITimeoutError

from app.core.config import Settings
from app.services.llm_service import LLMService
from app.services.model_runtime import ModelRuntime

BASE_ENV = {
    "OPENAI_API_KEY": "synthetic-platform-key",
    "OPENAI_BASE_URL": "https://platform.example/v1",
    "MODEL_NAME": "qwen3.8-flash",
    "EMBEDDING_MODEL": "embedding-model",
    "DATABASE_URL": "mysql+aiomysql://test:test@localhost/test",
    "OSS_ACCESS_KEY_ID": "test", "OSS_ACCESS_KEY_SECRET": "test",
    "OSS_ENDPOINT": "test", "OSS_BUCKET_NAME": "test",
}


def make_settings(**env):
    with patch.dict(os.environ, {**BASE_ENV, **env}, clear=True):
        return Settings(_env_file=None)


class FakeStream:
    def __init__(self, parts=(None, "", "hello", " world"), error=None):
        self.parts = parts
        self.error = error
        self.close = AsyncMock()

    async def __aiter__(self):
        yield SimpleNamespace(choices=[])
        for part in self.parts:
            yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=part))])
        if self.error:
            raise self.error


def fake_client():
    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="answer"))],
    ))
    client.embeddings.create = AsyncMock(return_value=SimpleNamespace(
        data=[SimpleNamespace(embedding=[0.5, 0.7])],
    ))
    client.close = AsyncMock()
    return client


class LLMServiceRoutingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.settings = make_settings()
        self.client = fake_client()
        self.factory = patch("app.services.llm_service.AsyncOpenAI", return_value=self.client).start()
        self.addCleanup(patch.stopall)
        patch("app.services.llm_service.get_settings", return_value=self.settings).start()
        self.service = LLMService()
        self.messages = [{"role": "user", "content": "hello"}]
        self.runtime = ModelRuntime("personal-model", "synthetic-personal-key", "https://personal.example/v1", "personal", 0.2, 123)

    async def test_chat_platform_defaults_and_client_closed(self):
        self.assertEqual(await self.service.chat(self.messages), "answer")
        self.factory.assert_called_once_with(api_key=BASE_ENV["OPENAI_API_KEY"], base_url=BASE_ENV["OPENAI_BASE_URL"], timeout=60, max_retries=0)
        self.client.chat.completions.create.assert_awaited_once_with(model="qwen3.8-flash", messages=self.messages, temperature=0.7, max_tokens=4096)
        self.client.close.assert_awaited_once()

    async def test_chat_legacy_model_override(self):
        await self.service.chat(self.messages, model="explicit", temperature=0.1, max_tokens=7)
        self.assertEqual(self.client.chat.completions.create.await_args.kwargs["model"], "explicit")

    async def test_personal_runtime_controls_model_key_and_parameters(self):
        await self.service.chat(self.messages, model="ignored", runtime=self.runtime)
        self.factory.assert_called_once_with(api_key=self.runtime.api_key, base_url=self.runtime.base_url, timeout=60, max_retries=0)
        self.client.chat.completions.create.assert_awaited_once_with(model="personal-model", messages=self.messages, temperature=0.2, max_tokens=123)
        self.assertNotIn(self.runtime.api_key, repr(self.runtime))

    async def test_stream_personal_routing_and_both_resources_closed(self):
        stream = FakeStream()
        self.client.chat.completions.create.return_value = stream
        parts = [p async for p in self.service.stream_chat(self.messages, runtime=self.runtime)]
        self.assertEqual(parts, ["hello", " world"])
        self.assertEqual(self.factory.call_args.kwargs["api_key"], self.runtime.api_key)
        self.client.chat.completions.create.assert_awaited_once_with(model="personal-model", messages=self.messages, temperature=0.2, max_tokens=123, stream=True)
        stream.close.assert_awaited_once()
        self.client.close.assert_awaited_once()

    async def test_stream_early_close_releases_resources(self):
        stream = FakeStream()
        self.client.chat.completions.create.return_value = stream
        generator = self.service.stream_chat(self.messages, runtime=self.runtime)
        await anext(generator)
        await generator.aclose()
        stream.close.assert_awaited_once()
        self.client.close.assert_awaited_once()

    async def test_invalid_key_timeout_and_provider_error_never_retry_or_fallback(self):
        request = httpx.Request("POST", self.runtime.base_url)
        failures = [
            AuthenticationError(self.runtime.api_key, response=httpx.Response(401, request=request), body={"key": self.runtime.api_key}),
            APITimeoutError(request=request),
            RuntimeError(f"Authorization: Bearer {self.runtime.api_key}"),
        ]
        for failure, status in zip(failures, [502, 504, 502]):
            for streaming in (False, True):
                with self.subTest(failure=type(failure).__name__, streaming=streaming):
                    self.factory.reset_mock(); self.client.close.reset_mock()
                    self.client.chat.completions.create.reset_mock()
                    self.client.chat.completions.create.side_effect = failure
                    with self.assertRaises(HTTPException) as caught:
                        if streaming:
                            _ = [x async for x in self.service.stream_chat(self.messages, runtime=self.runtime)]
                        else:
                            await self.service.chat(self.messages, runtime=self.runtime)
                    self.assertEqual(caught.exception.status_code, status)
                    self.assertNotIn(self.runtime.api_key, caught.exception.detail)
                    self.assertTrue(caught.exception.__suppress_context__)
                    self.assertEqual(self.factory.call_count, 1)
                    self.assertEqual(self.factory.call_args.kwargs["api_key"], self.runtime.api_key)
                    self.assertEqual(self.client.chat.completions.create.await_count, 1)
                    self.client.close.assert_awaited_once()

    async def test_midstream_error_is_sanitized_and_stream_closed(self):
        stream = FakeStream(error=RuntimeError(self.runtime.api_key))
        self.client.chat.completions.create.return_value = stream
        with self.assertRaises(HTTPException) as caught:
            _ = [x async for x in self.service.stream_chat(self.messages, runtime=self.runtime)]
        self.assertNotIn(self.runtime.api_key, caught.exception.detail)
        stream.close.assert_awaited_once(); self.client.close.assert_awaited_once()

    async def test_cancellation_closes_client(self):
        started = asyncio.Event()
        async def pending(**kwargs):
            started.set()
            await asyncio.Event().wait()
        self.client.chat.completions.create.side_effect = pending
        task = asyncio.create_task(self.service.chat(self.messages, runtime=self.runtime))
        await started.wait(); task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.client.close.assert_awaited_once()

    async def test_concurrent_users_get_separate_clients_and_credentials(self):
        clients = []
        ready = asyncio.Event()
        def construct(**options):
            client = fake_client()
            clients.append((options, client))
            async def answer(**kwargs):
                if len(clients) == 2:
                    ready.set()
                await ready.wait()
                return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=options["api_key"]))])
            client.chat.completions.create.side_effect = answer
            return client
        self.factory.side_effect = construct
        other = ModelRuntime("other-model", "synthetic-other-key", "https://other.example/v1", "personal")
        answers = await asyncio.gather(self.service.chat(self.messages, runtime=self.runtime), self.service.chat(self.messages, runtime=other))
        self.assertEqual(answers, [self.runtime.api_key, other.api_key])
        for (options, client), runtime in zip(clients, [self.runtime, other]):
            self.assertEqual(options["api_key"], runtime.api_key)
            self.assertEqual(client.chat.completions.create.await_args.kwargs["model"], runtime.model_key)
            client.close.assert_awaited_once()

    async def test_embedding_overrides_and_fallbacks_remain_platform_only(self):
        for base_url in (None, "", "https://embedding.example/v1"):
            for api_key in (None, "", "synthetic-embedding-key"):
                env = {}
                if base_url is not None: env["EMBEDDING_BASE_URL"] = base_url
                if api_key is not None: env["EMBEDDING_API_KEY"] = api_key
                settings = make_settings(**env)
                with patch("app.services.llm_service.get_settings", return_value=settings):
                    service = LLMService()
                self.factory.reset_mock(); self.client.close.reset_mock()
                self.assertEqual(await service.embed_text("text"), [0.5, 0.7])
                self.factory.assert_called_once_with(api_key=api_key or BASE_ENV["OPENAI_API_KEY"], base_url=base_url or BASE_ENV["OPENAI_BASE_URL"], timeout=60, max_retries=0)
                self.client.close.assert_awaited_once()
