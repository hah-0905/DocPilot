"""BYOK security and end-to-end routing using real SQL and bearer authentication.

All keys are synthetic, all databases in-memory, all provider SDK calls mocked.
"""
import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from cryptography.fernet import Fernet
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.personal_model import router as personal_router
from app.api.settings import router as settings_router
from app.core import redis as redis_module
from app.core.exception_handlers import register_exception_handlers
from app.db.session import get_db
from app.models.chat import ChatMessage, ChatSession
from app.models.documents import Document, DocumentChunk, DocumentVersion
from app.models.kb import KnowledgeBase
from app.models.report import ReportTask
from app.models.user_model_config import UserModelConfig
from app.models.users import User
from app.models.workspace_members import WorkspaceMember
from app.models.workspace_model_settings import WorkspaceModelSettings
from app.models.workspaces import Workspace
from app.schemas.personal_model import PersonalModelUpdate
from app.services.chat_service import ChatService
from app.services.llm_service import LLMService
from app.services.model_runtime import resolve_model_runtime
from app.services.personal_model_service import decrypt_key, personal_model_service
from app.services.reports.report_services import ReportService
from app.services.users_service import _credential_version
from tests.security_sqlite import SecuritySession, make_engine
from tests.test_llm_service import BASE_ENV, FakeStream, fake_client, make_settings
from tests.test_rag_chat_security import kb_api
from tests.test_user_account_security import MemoryTokenStore

with patch("app.services.chat_service.ChatService"):
    from app.api import chat as chat_api
with patch("app.services.reports.report_services.ReportService"):
    from app.api import report as report_api

ALICE_KEY = "synthetic-alice-key-A123"
BOB_KEY = "synthetic-bob-key-B456"
REPLACEMENT_KEY = "synthetic-replacement-key-C789"


class PersonalModelTests(unittest.TestCase):
    def setUp(self):
        self.settings = make_settings(
            PERSONAL_MODEL_MASTER_KEY=Fernet.generate_key().decode(),
            PLATFORM_MODELS='["platform-secondary"]',
            PERSONAL_MODEL_PROVIDERS=json.dumps([{
                "id": "other", "label": "Other test provider", "base_url": "https://other.example/v1",
                "models": ["personal-small", "personal-large"],
            }]),
        )
        for module in ["personal_model_service", "model_runtime", "model_catalog", "workspace_settings_service", "settings_service", "llm_service"]:
            replacement = patch(f"app.services.{module}.get_settings", return_value=self.settings)
            replacement.start(); self.addCleanup(replacement.stop)
        replacement = patch("app.api.personal_model.get_settings", return_value=self.settings)
        replacement.start(); self.addCleanup(replacement.stop)
        self.engine = make_engine()
        self.addCleanup(self.engine.dispose)
        with Session(self.engine) as db:
            db.add_all([User(id=i, username=f"user{i}", email=f"u{i}@example.com", password_hash="synthetic-hash") for i in (1, 2)])
            db.add_all([Workspace(id=10, name="Alice", owner_user_id=1), Workspace(id=20, name="Bob", owner_user_id=2)])
            db.add_all([WorkspaceMember(workspace_id=10, user_id=1, role="owner"), WorkspaceMember(workspace_id=20, user_id=2, role="owner"), WorkspaceMember(workspace_id=10, user_id=2, role="member")])
            db.add(KnowledgeBase(id=101, workspace_id=10, name="Alice KB", created_by=1))
            db.add(Document(id=11, kb_id=101, title="Synthetic source", created_by=1))
            db.add(DocumentVersion(id=110, document_id=11, version_no=1, created_by=1))
            db.add(DocumentChunk(id=1100, kb_id=101, document_id=11, version_id=110, chunk_no=0,
                                 chunk_uid="synthetic", content="synthetic reference", content_hash="a" * 64))
            db.commit()
        tokens = MemoryTokenStore()
        for token, user_id in [("alice", 1), ("bob", 2)]:
            tokens.values[f"login:token:{token}"] = json.dumps({"user_id": user_id, "credential_version": _credential_version("synthetic-hash")})
        replacement = patch.object(redis_module, "_redis_client", tokens)
        replacement.start(); self.addCleanup(replacement.stop)
        self.app = FastAPI()
        self.app.include_router(personal_router)
        self.app.include_router(settings_router)
        self.app.include_router(chat_api.router)
        self.app.include_router(report_api.router)
        self.app.include_router(kb_api.router)
        register_exception_handlers(self.app)
        async def isolated_db():
            async with SecuritySession(self.engine) as db:
                yield db
        self.app.dependency_overrides[get_db] = isolated_db
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)
        self.sdk_clients = []
        self.sdk_options = []
        def construct(**options):
            client = fake_client()
            self.sdk_clients.append(client); self.sdk_options.append(options)
            if self.sdk_failure:
                client.chat.completions.create.side_effect = self.sdk_failure
            elif self.streaming:
                client.chat.completions.create.return_value = FakeStream()
            return client
        self.streaming = False
        self.sdk_failure = None
        self.factory = patch("app.services.llm_service.AsyncOpenAI", side_effect=construct).start()
        self.addCleanup(patch.stopall)
        chat = ChatService.__new__(ChatService)
        chat.llm_service = LLMService()
        chat.rag_service = SimpleNamespace(search=AsyncMock(return_value=[]))
        report = ReportService.__new__(ReportService)
        report.llm_service = LLMService()
        report.rag_service = SimpleNamespace(search=AsyncMock(return_value=[{
            "content": "synthetic reference", "document_id": 11, "chunk_id": 1100,
        }]))
        for module, name, service in [(chat_api, "chat_service", chat), (report_api, "report_service", report)]:
            replacement = patch.object(module, name, service)
            replacement.start(); self.addCleanup(replacement.stop)

    def request(self, method, suffix="", *, token="alice", **kwargs):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return self.client.request(method, f"/api/settings/personal-model{suffix}", headers=headers, **kwargs)

    def save(self, *, token="alice", key=ALICE_KEY, **overrides):
        payload = {"provider_id": "other", "model_name": "personal-small", "enabled": True, **overrides}
        if key is not None: payload["api_key"] = key
        return self.request("PUT", token=token, json=payload)

    def row(self, user_id=1):
        with Session(self.engine) as db:
            row = db.get(UserModelConfig, user_id)
            if row: db.expunge(row)
            return row

    def assert_no_key(self, value):
        for key in (ALICE_KEY, BOB_KEY, REPLACEMENT_KEY):
            self.assertNotIn(key, str(value))

    def test_all_personal_endpoints_require_actual_bearer_authentication(self):
        for method, suffix, payload in [("GET", "", None), ("PUT", "", {"provider_id": "other", "model_name": "personal-small", "api_key": ALICE_KEY}), ("POST", "/test", {"provider_id": "other", "model_name": "personal-small", "api_key": ALICE_KEY}), ("DELETE", "", None)]:
            response = self.request(method, suffix, token=None, json=payload)
            self.assertIn(response.status_code, {401, 403})
        self.assertIsNone(self.row()); self.factory.assert_not_called()

    def test_encrypted_storage_masked_status_and_no_cache(self):
        response = self.save()
        self.assertEqual(response.status_code, 200, response.text)
        self.assert_no_key(response.text)
        self.assertEqual(response.json()["key_mask"], "••••A123")
        self.assertEqual(response.headers["cache-control"], "no-store")
        row = self.row()
        self.assertNotIn(ALICE_KEY, row.encrypted_credential)
        self.assertEqual(decrypt_key(row), ALICE_KEY)
        self.assertEqual(row.credential_last_four, "A123")
        read = self.request("GET")
        self.assert_no_key(read.text)
        self.assertNotIn(row.encrypted_credential, read.text)
        self.factory.assert_not_called()

    def test_cross_user_read_update_test_delete_cannot_target_another_account(self):
        self.assertEqual(self.save().status_code, 200)
        self.assertFalse(self.request("GET", token="bob").json()["configured"])
        forged = self.save(token="bob", user_id=1)
        self.assertEqual(forged.status_code, 422)
        self.assertEqual(self.request("GET", "/1", token="bob").status_code, 404)
        response = self.request("POST", "/test", token="bob", json={"provider_id": "other", "model_name": "personal-small"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.request("DELETE", token="bob").status_code, 200)
        self.assertEqual(decrypt_key(self.row()), ALICE_KEY)
        self.assertEqual(self.save(token="bob", key=BOB_KEY).status_code, 200)
        self.assertEqual(decrypt_key(self.row(2)), BOB_KEY)
        self.assertEqual(decrypt_key(self.row(1)), ALICE_KEY)
        self.factory.assert_not_called()

    def test_update_omitted_or_null_key_preserves_replacement_and_deletion(self):
        self.save()
        original_ciphertext = self.row().encrypted_credential
        self.assertEqual(self.save(key=None, model_name="personal-large", enabled=False).status_code, 200)
        self.assertEqual(self.row().encrypted_credential, original_ciphertext)
        self.assertEqual(self.request("PUT", json={"provider_id": "other", "model_name": "personal-small", "api_key": None}).status_code, 200)
        self.assertEqual(self.row().encrypted_credential, original_ciphertext)
        self.assertEqual(self.save(key=REPLACEMENT_KEY).status_code, 200)
        self.assertEqual(decrypt_key(self.row()), REPLACEMENT_KEY)
        self.assert_no_key(self.request("GET").text)
        self.assertEqual(self.request("DELETE").status_code, 200)
        self.assertIsNone(self.row())
        self.assertFalse(self.request("GET").json()["configured"])
        self.assertEqual(self.save(key=None).status_code, 422)

    def test_changing_provider_requires_replacement_key(self):
        self.save()
        response = self.save(key=None, provider_id="platform", model_name="qwen3.8-flash")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.row().provider_id, "other")

    def test_validation_errors_and_logs_never_echo_secrets(self):
        bad_payloads = [
            {"api_key": "short"}, {"api_key": [ALICE_KEY]}, {"api_key": {ALICE_KEY: ALICE_KEY}},
            {"model_name": ALICE_KEY}, {ALICE_KEY: ALICE_KEY}, {"base_url": ALICE_KEY},
            {"provider_id": ALICE_KEY}, {"api_key": ALICE_KEY + "\n"},
        ]
        for overrides in bad_payloads:
            with self.subTest(fields=list(overrides)):
                with self.assertLogs("app.core.exception_handlers", level="WARNING") as logs:
                    response = self.save(**{"key": None, **overrides})
                self.assertEqual(response.status_code, 422)
                self.assert_no_key(response.text); self.assert_no_key(logs.output)
        self.factory.assert_not_called()

    def test_large_or_malformed_request_is_sanitized(self):
        for content, expected in [("x" * 8193, 413), ('{"api_key":"' + ALICE_KEY, 422)]:
            response = self.client.put("/api/settings/personal-model", content=content, headers={"Authorization": "Bearer alice", "Content-Type": "application/json"})
            self.assertEqual(response.status_code, expected)
            self.assert_no_key(response.text)

    def test_catalog_includes_actual_default_and_validates_provider_membership(self):
        response = self.client.get("/api/settings/model-catalog", headers={"Authorization": "Bearer alice"})
        directory = response.json()
        self.assertEqual(directory["platform_default_model"], "qwen3.8-flash")
        self.assertEqual(directory["platform_models"], ["qwen3.8-flash", "platform-secondary"])
        self.assertNotIn("base_url", str(directory)); self.assert_no_key(directory)
        self.assertEqual(self.save(model_name="qwen3.8-flash").status_code, 422)
        self.assertEqual(self.save(provider_id="unknown").status_code, 422)
        self.factory.assert_not_called()

    def test_ciphertext_authentication_and_owner_binding(self):
        self.save(); self.save(token="bob", key=BOB_KEY)
        row = self.row()
        row.encrypted_credential = self.row(2).encrypted_credential
        with self.assertRaises(HTTPException): decrypt_key(row)
        row = self.row(); row.encrypted_credential = row.encrypted_credential[:-8] + "AAAAAAAA"
        with self.assertRaises(HTTPException): decrypt_key(row)

    def resolve(self, user_id=1, workspace_id=10):
        async def run():
            async with SecuritySession(self.engine) as db:
                return await resolve_model_runtime(db, user_id, workspace_id)
        return asyncio.run(run())

    def test_runtime_platform_workspace_personal_and_disabled(self):
        self.assertEqual((self.resolve().source, self.resolve().model_key, self.resolve().api_key), ("platform", "qwen3.8-flash", BASE_ENV["OPENAI_API_KEY"]))
        with Session(self.engine) as db:
            db.add(WorkspaceModelSettings(workspace_id=10, model_key="platform-secondary", temperature=0.2, max_tokens=77)); db.commit()
        self.assertEqual(self.resolve().model_key, "platform-secondary")
        self.save()
        runtime = self.resolve()
        self.assertEqual((runtime.source, runtime.model_key, runtime.api_key, runtime.base_url, runtime.temperature, runtime.max_tokens), ("personal", "personal-small", ALICE_KEY, "https://other.example/v1", 0.2, 77))
        self.assertEqual(self.resolve(2, 20).api_key, BASE_ENV["OPENAI_API_KEY"])
        self.save(key=None, enabled=False)
        self.assertEqual(self.resolve().api_key, BASE_ENV["OPENAI_API_KEY"])

    def test_missing_or_invalid_master_key_platform_keeps_working(self):
        self.save()
        for missing in (None, "", "invalid"):
            from pydantic import SecretStr
            self.settings.personal_model_master_key = SecretStr(missing) if missing is not None else None
            status = self.request("GET").json()
            self.assertFalse(status["available"])
            self.assertEqual(self.save().status_code, 503)
            response = self.request("POST", "/test", json={"provider_id": "other", "model_name": "personal-small", "api_key": ALICE_KEY})
            self.assertEqual(response.status_code, 503)
            with self.assertRaises(HTTPException) as error: self.resolve()
            self.assertEqual(error.exception.status_code, 503)
            self.assertEqual(self.resolve(2, 20).source, "platform")
        self.assertEqual(self.request("DELETE").status_code, 200)
        self.assertEqual(self.resolve().source, "platform")
        self.factory.assert_not_called()

    def test_rotated_master_key_cannot_silently_fallback(self):
        self.save()
        from pydantic import SecretStr
        self.settings.personal_model_master_key = SecretStr(Fernet.generate_key().decode())
        with self.assertRaises(HTTPException) as error: self.resolve()
        self.assertEqual(error.exception.status_code, 503)
        self.factory.assert_not_called()

    def test_connection_uses_bounded_probe_and_does_not_save(self):
        response = self.request("POST", "/test", json={"provider_id": "other", "model_name": "personal-small", "api_key": ALICE_KEY})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIsNone(self.row()); self.assert_no_key(response.text)
        self.assertEqual(self.sdk_options[0], {"api_key": ALICE_KEY, "base_url": "https://other.example/v1", "timeout": 10, "max_retries": 0})
        params = self.sdk_clients[0].chat.completions.create.await_args.kwargs
        self.assertEqual((params["model"], params["max_tokens"], params["temperature"]), ("personal-small", 16, 0))
        self.assertEqual(params["messages"], [{"role": "user", "content": "Reply OK."}])
        self.sdk_clients[0].close.assert_awaited_once()

    def test_connection_existing_key_failure_timeout_and_unsupported_model_no_fallback(self):
        self.save()
        for failure, code in [(RuntimeError(ALICE_KEY), 502), (TimeoutError(ALICE_KEY), 504)]:
            self.sdk_failure = failure
            response = self.request("POST", "/test", json={"provider_id": "other", "model_name": "personal-small"})
            self.assertEqual(response.status_code, code)
            self.assert_no_key(response.text)
        before = self.factory.call_count
        self.assertEqual(self.request("POST", "/test", json={"provider_id": "other", "model_name": "unsupported", "api_key": ALICE_KEY}).status_code, 422)
        self.assertEqual(self.factory.call_count, before)
        self.assertTrue(all(option["api_key"] == ALICE_KEY for option in self.sdk_options))
        self.assertEqual(decrypt_key(self.row()), ALICE_KEY)

    def test_connection_total_deadline_is_enforced_without_waiting_for_real_network(self):
        self.save()
        real_timeout = asyncio.timeout
        async def blocked(*args, **kwargs):
            await asyncio.Event().wait()
        with patch("app.services.personal_model_service.asyncio.timeout", side_effect=lambda seconds: real_timeout(0.01)) as deadline, patch.object(LLMService, "chat", side_effect=blocked):
            response = self.request("POST", "/test", json={"provider_id": "other", "model_name": "personal-small"})
        self.assertEqual(response.status_code, 504)
        deadline.assert_called_once_with(12)
        self.factory.assert_not_called()

    def chat(self, *, stream=False, token="alice", **overrides):
        self.streaming = stream
        return self.client.post("/api/chat/completions", json={"message": "test", "stream": stream, **overrides}, headers={"Authorization": f"Bearer {token}"})

    def report(self, **overrides):
        return self.client.post("/api/report/tasks", json={"title": "Test", "workspace_id": 10, "kb_id": 101, "length": "short", **overrides}, headers={"Authorization": "Bearer alice"})

    def test_chat_stream_report_use_personal_credentials_and_persist_actual_model(self):
        self.save()
        self.assertEqual(self.chat().status_code, 200)
        stream = self.chat(stream=True)
        self.assertIn("hello", stream.text); self.assertIn("[DONE]", stream.text)
        self.streaming = False
        response = self.report(model_name="legacy-ignored-label")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(self.sdk_options), 5)
        for options, client in zip(self.sdk_options, self.sdk_clients):
            self.assertEqual(options["api_key"], ALICE_KEY)
            self.assertEqual(client.chat.completions.create.await_args.kwargs["model"], "personal-small")
            client.close.assert_awaited_once()
        with Session(self.engine) as db:
            self.assertEqual({m.model_name for m in db.scalars(select(ChatMessage).where(ChatMessage.role == "assistant"))}, {"personal-small"})
            self.assertEqual(db.scalar(select(ReportTask)).model_name, "personal-small")

    def test_chat_stream_report_use_workspace_platform_config(self):
        with Session(self.engine) as db:
            db.add(WorkspaceModelSettings(workspace_id=10, model_key="platform-secondary")); db.commit()
        self.assertEqual(self.chat().status_code, 200)
        self.assertIn("hello", self.chat(stream=True).text)
        self.streaming = False
        self.assertEqual(self.report().status_code, 200)
        for options, client in zip(self.sdk_options, self.sdk_clients):
            self.assertEqual(options["api_key"], BASE_ENV["OPENAI_API_KEY"])
            self.assertEqual(client.chat.completions.create.await_args.kwargs["model"], "platform-secondary")

    def test_personal_key_on_platform_provider_does_not_change_embedding_credentials(self):
        response = self.save(provider_id="platform", model_name="qwen3.8-flash")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.chat().status_code, 200)
        self.assertEqual(self.sdk_options[0]["base_url"], BASE_ENV["OPENAI_BASE_URL"])
        self.assertEqual(self.sdk_options[0]["api_key"], ALICE_KEY)
        asyncio.run(chat_api.chat_service.llm_service.embed_text("synthetic text"))
        self.assertEqual(self.sdk_options[1]["api_key"], BASE_ENV["OPENAI_API_KEY"])
        self.sdk_clients[1].embeddings.create.assert_awaited_once()

    def test_two_users_concurrent_chat_resolves_and_uses_only_their_own_credentials(self):
        self.save(); self.save(token="bob", key=BOB_KEY, model_name="personal-large")
        with Session(self.engine) as db:
            db.add_all([ChatSession(id=111, user_id=1, workspace_id=10, title="Alice"),
                        ChatSession(id=222, user_id=2, workspace_id=20, title="Bob")])
            db.commit()
        async def run():
            ready = asyncio.Event()
            seen = []
            def construct(**options):
                client = fake_client()
                seen.append((options, client))
                async def answer(**kwargs):
                    if len(seen) == 2:
                        ready.set()
                    await ready.wait()
                    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
                        content=f"answer for {kwargs['model']}",
                    ))])
                client.chat.completions.create.side_effect = answer
                return client
            self.factory.side_effect = construct
            async with SecuritySession(self.engine) as alice_db, SecuritySession(self.engine) as bob_db:
                answers = await asyncio.wait_for(asyncio.gather(
                    chat_api.chat_service.chat(alice_db, SimpleNamespace(id=1), 111, "Alice test"),
                    chat_api.chat_service.chat(bob_db, SimpleNamespace(id=2), 222, "Bob test"),
                ), timeout=2)
            self.assertEqual([a["answer"] for a in answers], ["answer for personal-small", "answer for personal-large"])
            self.assertEqual([o["api_key"] for o, c in seen], [ALICE_KEY, BOB_KEY])
            for _, client in seen: client.close.assert_awaited_once()
        asyncio.run(run())

    def test_chat_report_and_sse_errors_are_explicit_sanitized_and_never_fallback(self):
        self.save(); self.sdk_failure = RuntimeError(ALICE_KEY)
        chat = self.chat(); self.assertEqual(chat.status_code, 502); self.assert_no_key(chat.text)
        stream = self.chat(stream=True); self.assertIn("event: error", stream.text); self.assert_no_key(stream.text)
        self.streaming = False
        report = self.report(); self.assertEqual(report.status_code, 502); self.assert_no_key(report.text)
        self.assertEqual(len(self.sdk_options), 3)
        self.assertTrue(all(o["api_key"] == ALICE_KEY for o in self.sdk_options))
        with Session(self.engine) as db:
            self.assertEqual(len(db.scalars(select(ReportTask)).all()), 0)
            self.assertEqual(len(db.scalars(select(ChatMessage)).all()), 0)

    def test_chat_ownership_is_preserved_with_byok(self):
        self.save(token="bob", key=BOB_KEY)
        first = self.chat().json()["data"]["session_id"]
        self.factory.reset_mock()
        self.assertEqual(self.chat(token="bob", session_id=first).status_code, 404)
        self.assertEqual(self.chat(token="bob", kb_id=101).status_code, 404)
        self.factory.assert_not_called()

    def test_closing_chat_stream_releases_nested_provider_stream_and_client(self):
        self.save(); self.streaming = True
        async def run():
            async with SecuritySession(self.engine) as db:
                generator = chat_api.chat_service.stream_chat(db, SimpleNamespace(id=1), None, "test")
                self.assertEqual((await anext(generator))["type"], "meta")
                self.assertEqual(await anext(generator), "hello")
                await generator.aclose()
                provider_stream = self.sdk_clients[0].chat.completions.create.return_value
                provider_stream.close.assert_awaited_once()
                self.sdk_clients[0].close.assert_awaited_once()
                await db.rollback()
        asyncio.run(run())

    def test_invalid_provider_directory_cannot_expose_urls_or_credentials(self):
        from app.core.config import ModelProvider
        for url in ("http://untrusted.example/v1", "https://user:password@untrusted.example/v1",
                    "https://untrusted.example/v1?key=" + ALICE_KEY):
            self.settings.personal_model_providers = [ModelProvider(id="other", label="Other", base_url=url, models=["personal-small"])]
            response = self.client.get("/api/settings/model-catalog", headers={"Authorization": "Bearer alice"})
            self.assertEqual(response.status_code, 503)
            self.assertNotIn(url, response.text); self.assert_no_key(response.text)
            self.assertEqual(self.resolve().source, "platform")
        self.factory.assert_not_called()

    def test_removed_personal_model_and_stale_workspace_model_fail_before_provider_call(self):
        self.save()
        with Session(self.engine) as db:
            db.get(UserModelConfig, 1).model_name = "removed-model"; db.commit()
        self.assertEqual(self.chat().status_code, 422)
        self.assertEqual(self.report().status_code, 422)
        self.request("DELETE")
        with Session(self.engine) as db:
            db.add(WorkspaceModelSettings(workspace_id=10, model_key="stale-model")); db.commit()
        self.assertEqual(self.chat().status_code, 422)
        self.factory.assert_not_called()

    def test_workspace_first_partial_update_inherits_platform_default_and_preserves_roles(self):
        response = self.client.put("/api/settings/model/10", json={"temperature": 0.4}, headers={"Authorization": "Bearer alice"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["model_key"], "qwen3.8-flash")
        for user, workspace in [("bob", 10), ("alice", 20), ("alice", 999)]:
            for method in ("GET", "PUT"):
                kwargs = {"json": {"model_key": "qwen3.8-flash"}} if method == "PUT" else {}
                response = self.client.request(method, f"/api/settings/model/{workspace}", headers={"Authorization": f"Bearer {user}"}, **kwargs)
                self.assertEqual(response.status_code, 403)
        response = self.client.put("/api/settings/model/10", json={"model_key": "deepseek-chat"}, headers={"Authorization": "Bearer alice"})
        self.assertEqual(response.status_code, 422)
