"""RAG route authorization with real ownership SQL and isolated model calls."""

from datetime import datetime
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.exception_handlers import register_exception_handlers
from app.db.session import get_db
from app.models.kb import KnowledgeBase
from app.models.workspaces import Workspace
from app.services.rag_service import RagService
from app.services.users_service import get_current_user
from tests.test_user_account_security import SQLiteAsyncSession

# Loading the router must not open the project's Chroma files or construct
# unrelated external services. The route's real KbService remains in use.
with (
    patch("app.services.document_service.DocumentService"),
    patch("app.services.rag_service.RagService"),
    patch("app.services.document_task_service.DocumentTaskService"),
):
    from app.api import kb as kb_api


class RagChatSecurityTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        self.addCleanup(self.engine.dispose)
        with self.engine.begin() as connection:
            connection.exec_driver_sql("""
                CREATE TABLE workspaces (
                    id INTEGER PRIMARY KEY, name TEXT, description TEXT,
                    owner_user_id INTEGER, status TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    deleted_at DATETIME
                )
            """)
            connection.exec_driver_sql("""
                CREATE TABLE knowledge_bases (
                    id INTEGER PRIMARY KEY, workspace_id INTEGER, name TEXT,
                    description TEXT, visibility TEXT, embedding_model TEXT,
                    rerank_model TEXT, chunk_strategy TEXT, chunk_size INTEGER,
                    chunk_overlap INTEGER, default_top_k INTEGER, status TEXT,
                    created_by INTEGER, created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP, deleted_at DATETIME
                )
            """)
        with Session(self.engine) as db:
            db.add_all([
                Workspace(id=10, name="Alice", owner_user_id=1, status="active"),
                Workspace(id=20, name="Bob", owner_user_id=2, status="active"),
                Workspace(id=30, name="Disabled", owner_user_id=1, status="disabled"),
                Workspace(id=40, name="Deleted", owner_user_id=1, status="deleted"),
            ])
            for kb_id, workspace_id, status, visibility in [
                (101, 10, "active", "private"), (102, 20, "active", "private"),
                (103, 10, "deleted", "private"), (104, 10, "disabled", "private"),
                (105, 30, "active", "private"), (106, 40, "active", "private"),
                (107, 10, "active", "public"), (108, 20, "active", "public"),
            ]:
                db.add(KnowledgeBase(
                    id=kb_id, workspace_id=workspace_id, name=f"KB {kb_id}",
                    status=status, visibility=visibility, created_by=1,
                    deleted_at=datetime(2026, 10, 8) if status == "deleted" else None,
                ))
            db.commit()

        self.references = [{"chunk_id": 1, "document_id": 2, "content": "synthetic source", "score": 0.9}]
        self.rag = RagService.__new__(RagService)
        self.rag.search = AsyncMock(return_value=self.references)
        self.rag.llm_service = SimpleNamespace(chat=AsyncMock(return_value="synthetic answer"))
        rag_patch = patch.object(kb_api, "rag_service", self.rag)
        rag_patch.start()
        self.addCleanup(rag_patch.stop)

        app = FastAPI()
        app.include_router(kb_api.router)
        register_exception_handlers(app)

        async def isolated_db():
            db = SQLiteAsyncSession(self.engine)
            try:
                yield db
            finally:
                db.session.close()

        app.dependency_overrides[get_db] = isolated_db
        # Authorization tests use Alice; the anonymous test removes this
        # override to exercise the route's actual bearer dependency.
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)
        self.app = app
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def ask(self, kb_id, **payload):
        return self.client.post(f"/api/kb/knowledge-bases/{kb_id}/chat", json={
            "kb_id": kb_id, "question": "test question", "top_k": 3, **payload,
        })

    def assert_no_generation(self):
        self.rag.search.assert_not_awaited()
        self.rag.llm_service.chat.assert_not_awaited()

    def test_anonymous_request_is_rejected_before_retrieval(self):
        del self.app.dependency_overrides[get_current_user]
        response = self.ask(101)
        self.assertIn(response.status_code, {401, 403})
        self.assert_no_generation()

    def test_other_users_private_knowledge_base_is_not_accessible(self):
        response = self.ask(102)
        self.assertEqual(response.status_code, 404)
        self.assertNotIn("references", response.json())
        self.assert_no_generation()

    def test_path_body_mismatch_is_rejected_in_both_directions(self):
        for path_id, body_id in [(101, 102), (102, 101)]:
            with self.subTest(path_id=path_id, body_id=body_id):
                response = self.client.post(f"/api/kb/knowledge-bases/{path_id}/chat", json={
                    "kb_id": body_id, "question": "test question",
                })
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json()["message"], "知识库 ID 不一致")
        self.assert_no_generation()

    def test_missing_knowledge_base_is_not_accessible(self):
        self.assertEqual(self.ask(999).status_code, 404)
        self.assert_no_generation()

    def test_deleted_or_disabled_knowledge_base_is_not_accessible(self):
        for kb_id in (103, 104):
            with self.subTest(kb_id=kb_id):
                self.assertEqual(self.ask(kb_id).status_code, 404)
        self.assert_no_generation()

    def test_inactive_workspace_is_not_accessible(self):
        for kb_id in (105, 106):
            with self.subTest(kb_id=kb_id):
                self.assertEqual(self.ask(kb_id).status_code, 404)
        self.assert_no_generation()

    def test_public_flag_does_not_bypass_existing_owner_policy(self):
        self.assertEqual(self.ask(108).status_code, 404)
        self.assert_no_generation()

    def test_owner_gets_existing_answer_and_references_contract(self):
        response = self.ask(101)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["data"], {
            "answer": "synthetic answer", "references": self.references,
        })
        self.assertEqual(self.rag.search.await_args.kwargs, {
            "kb_id": 101, "query": "test question", "top_k": 3,
        })
        self.rag.llm_service.chat.assert_awaited_once()

    def test_owner_can_query_own_public_knowledge_base(self):
        self.assertEqual(self.ask(107).status_code, 200)
        self.assertEqual(self.rag.search.await_args.kwargs["kb_id"], 107)

    def test_invalid_question_and_top_k_are_rejected_before_generation(self):
        for payload in ({"question": ""}, {"top_k": 0}, {"top_k": 21}):
            with self.subTest(payload=payload):
                self.assertEqual(self.ask(101, **payload).status_code, 422)
        self.assert_no_generation()


if __name__ == "__main__":
    unittest.main()
