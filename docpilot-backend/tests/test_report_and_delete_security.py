"""Cross-tenant report/deletion regressions with actual ORM queries and writes."""

import asyncio
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Session

from app.core.exception_handlers import register_exception_handlers
from app.db.session import get_db
from app.models.chunk_embeddings import ChunkEmbedding
from app.models.documents import Document, DocumentChunk, DocumentVersion
from app.models.kb import KnowledgeBase
from app.models.report import ReportSource, ReportTask
from app.models.users import User
from app.models.workspaces import Workspace
from app.schemas.report import ReportTaskCreate
from app.services.reports.report_services import ReportService
from app.services.users_service import get_current_user
from tests.document_service_fakes import FakeVectorService, make_service
from tests.security_sqlite import SecuritySession, make_engine
from tests.test_rag_chat_security import kb_api

with patch("app.services.reports.report_services.ReportService"):
    from app.api import report as report_api


class ResourceSecurityFixture(unittest.TestCase):
    def setUp(self):
        self.engine = make_engine()
        self.addCleanup(self.engine.dispose)
        with Session(self.engine) as db:
            db.add_all([
                User(id=i, username=f"user{i}", email=f"u{i}@example.com", password_hash="test")
                for i in (1, 2)
            ])
            db.add_all([
                Workspace(id=10, name="Alice", owner_user_id=1),
                Workspace(id=20, name="Bob", owner_user_id=2),
                Workspace(id=30, name="Alice other", owner_user_id=1),
                Workspace(id=40, name="Disabled", owner_user_id=1, status="disabled"),
            ])
            for kb_id, workspace_id, status in [(101, 10, "active"), (102, 20, "active"), (103, 10, "deleted"), (104, 40, "active"), (105, 10, "disabled")]:
                db.add(KnowledgeBase(id=kb_id, workspace_id=workspace_id, name=f"KB{kb_id}", created_by=1, status=status))
            for doc_id, kb_id, owner_id in [(11, 101, 1), (22, 102, 2)]:
                db.add(Document(id=doc_id, kb_id=kb_id, title=f"doc{doc_id}", created_by=owner_id, current_version_id=doc_id * 10, parse_status="success", index_status="indexed"))
                for number in (1, 2):
                    db.add(DocumentVersion(id=doc_id * 10 + number - 1, document_id=doc_id, version_no=number, created_by=owner_id, status="success"))
                db.add(DocumentChunk(id=doc_id * 100, kb_id=kb_id, document_id=doc_id, version_id=doc_id * 10, chunk_no=0, chunk_uid=f"chunk{doc_id}", content="synthetic source", content_hash="a" * 64))
                db.add(ChunkEmbedding(kb_id=kb_id, chunk_id=doc_id * 100, vector_id=f"v{doc_id}", vector_store_type="fake", vector_collection="test", embedding_model="fake", embedding_dim=2, content_hash="a" * 64))
            db.commit()

        self.app = FastAPI()
        register_exception_handlers(self.app)

        async def isolated_db():
            async with SecuritySession(self.engine) as db:
                yield db

        self.app.dependency_overrides[get_db] = isolated_db
        self.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)

    def start_client(self, router):
        self.app.include_router(router)
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)


class ReportSecurityTests(ResourceSecurityFixture):
    def setUp(self):
        super().setUp()
        self.service = ReportService.__new__(ReportService)
        self.service.rag_service = SimpleNamespace(search=AsyncMock(return_value=[{
            "document_id": 11, "chunk_id": 1100, "content": "synthetic source", "score": 0.9,
        }]))
        self.service.llm_service = SimpleNamespace(chat=AsyncMock(return_value="synthetic report"))
        replacement = patch.object(report_api, "report_service", self.service)
        replacement.start()
        self.addCleanup(replacement.stop)
        self.start_client(report_api.router)

    def create(self, **overrides):
        return self.client.post("/api/report/tasks", json={
            "title": "Test", "workspace_id": 10, "kb_id": 101, "length": "short", **overrides,
        })

    def assert_no_side_effects(self):
        self.service.rag_service.search.assert_not_awaited()
        self.service.llm_service.chat.assert_not_awaited()
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(ReportTask)), 0)
            self.assertEqual(db.scalar(select(func.count()).select_from(ReportSource)), 0)

    def test_anonymous_request_has_no_side_effects(self):
        del self.app.dependency_overrides[get_current_user]
        self.assertIn(self.create().status_code, {401, 403})
        self.assert_no_side_effects()

    def test_own_workspace_with_other_users_knowledge_base_is_rejected(self):
        self.assertEqual(self.create(kb_id=102).status_code, 404)
        self.assert_no_side_effects()

    def test_other_users_matching_workspace_and_knowledge_base_is_rejected(self):
        self.assertEqual(self.create(kb_id=102, workspace_id=20).status_code, 404)
        self.assert_no_side_effects()

    def test_forged_workspace_is_rejected_even_if_both_resources_are_owned(self):
        for workspace_id in (20, 30, 999):
            with self.subTest(workspace_id=workspace_id):
                self.assertEqual(self.create(workspace_id=workspace_id).status_code, 422)
        self.assert_no_side_effects()

    def test_missing_deleted_disabled_or_inactive_resources_are_rejected(self):
        for kb_id in (103, 104, 105, 999):
            with self.subTest(kb_id=kb_id):
                self.assertEqual(self.create(kb_id=kb_id).status_code, 404)
        self.assert_no_side_effects()

    def test_direct_service_creation_cannot_bypass_authorization(self):
        async def attempt():
            async with SecuritySession(self.engine) as db:
                with self.assertRaises(HTTPException) as error:
                    await self.service.create_report_task(db, ReportTaskCreate(title="Test", workspace_id=10, kb_id=102), user_id=1)
                self.assertEqual(error.exception.status_code, 404)
        asyncio.run(attempt())
        self.assert_no_side_effects()

    def test_valid_request_persists_only_authorized_sources(self):
        response = self.create()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "success")
        with Session(self.engine) as db:
            task = db.get(ReportTask, response.json()["task_id"])
            self.assertEqual((task.user_id, task.workspace_id, task.config["kb_id"]), (1, 10, 101))
            sources = db.scalars(select(ReportSource)).all()
            self.assertEqual(len(sources), 3)
            self.assertTrue(all(source.kb_id == 101 and source.document_id == 11 for source in sources))
        self.assertEqual(self.service.llm_service.chat.await_count, 3)

    def test_retrieval_rechecks_access_and_task_resource_binding(self):
        async def attempt():
            for kb_id, workspace_id, config_kb, expected in [(102, 20, 102, 404), (101, 30, 101, 422), (101, 10, 102, 422), (103, 10, 103, 404)]:
                async with SecuritySession(self.engine) as db:
                    task = SimpleNamespace(user_id=1, workspace_id=workspace_id, config={"kb_id": config_kb})
                    with self.assertRaises(HTTPException) as error:
                        await self.service.retrieve_section_chunks(db, kb_id, task, "title", "requirement", 5)
                    self.assertEqual(error.exception.status_code, expected)
        asyncio.run(attempt())
        self.assert_no_side_effects()


class DocumentDeleteSecurityTests(ResourceSecurityFixture):
    def setUp(self):
        super().setUp()
        self.vector = FakeVectorService()
        self.service = make_service(vector=self.vector)
        replacement = patch.object(kb_api, "document_service", self.service)
        replacement.start()
        self.addCleanup(replacement.stop)
        self.start_client(kb_api.router)

    def delete(self, kb_id=101, document_id=11):
        return self.client.delete(f"/api/kb/knowledge-bases/{kb_id}/documents/{document_id}")

    def assert_unchanged(self):
        self.assertEqual(self.vector.deletions, [])
        with Session(self.engine) as db:
            self.assertTrue(all(doc.enabled and doc.deleted_at is None for doc in db.scalars(select(Document))))
            self.assertTrue(all(version.status == "success" for version in db.scalars(select(DocumentVersion))))
            self.assertTrue(all(chunk.enabled for chunk in db.scalars(select(DocumentChunk))))

    def test_own_kb_with_other_users_document_cannot_update_versions(self):
        self.assertEqual(self.delete(document_id=22).status_code, 404)
        self.assert_unchanged()

    def test_other_users_matching_kb_and_document_are_rejected(self):
        self.assertEqual(self.delete(kb_id=102, document_id=22).status_code, 404)
        self.assert_unchanged()

    def test_missing_document_is_not_reported_as_success(self):
        self.assertEqual(self.delete(document_id=999).status_code, 404)
        self.assert_unchanged()

    def test_anonymous_delete_is_rejected(self):
        del self.app.dependency_overrides[get_current_user]
        self.assertIn(self.delete().status_code, {401, 403})
        self.assert_unchanged()

    def test_valid_delete_only_changes_target_document_and_versions(self):
        response = self.delete()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["data"], {"document_id": 11, "deleted": True})
        self.assertEqual(self.vector.deletions, [["v11"]])
        with Session(self.engine) as db:
            self.assertFalse(db.get(Document, 11).enabled)
            self.assertIsNotNone(db.get(Document, 11).deleted_at)
            self.assertTrue(db.get(Document, 22).enabled)
            self.assertFalse(db.get(DocumentChunk, 1100).enabled)
            self.assertTrue(db.get(DocumentChunk, 2200).enabled)
            self.assertTrue(all(v.status == ("deleted" if v.document_id == 11 else "success") for v in db.scalars(select(DocumentVersion))))
        # Repeat deletion must not trigger another vector call.
        self.assertEqual(self.delete().status_code, 404)
        self.assertEqual(len(self.vector.deletions), 1)

    def test_disabled_document_is_rejected_without_vector_calls(self):
        with Session(self.engine) as db:
            db.get(Document, 11).enabled = False
            db.commit()
        self.assertEqual(self.delete().status_code, 404)
        self.assertEqual(self.vector.deletions, [])
        with Session(self.engine) as db:
            self.assertEqual(db.get(DocumentVersion, 110).status, "success")

    def test_deletion_uses_current_locking_reads_for_document_and_vectors(self):
        async def run():
            async with SecuritySession(self.engine) as db:
                self.assertTrue(await self.service.delete_document(db, user_id=1, kb_id=101, document_id=11))
                selects = [str(statement.compile(dialect=mysql.dialect())) for statement in db.statements if statement.is_select]
                self.assertTrue(any("FROM documents" in sql and "FOR UPDATE" in sql for sql in selects))
                self.assertTrue(any("JOIN document_chunks" in sql and "FOR UPDATE" in sql for sql in selects))
        asyncio.run(run())

    def test_vector_deletion_failure_rolls_back_relational_changes(self):
        self.vector.delete_vectors = AsyncMock(side_effect=RuntimeError("vector unavailable"))

        async def attempt():
            async with SecuritySession(self.engine) as db:
                with self.assertRaisesRegex(RuntimeError, "vector unavailable"):
                    await self.service.delete_document(db, user_id=1, kb_id=101, document_id=11)
                await db.rollback()

        asyncio.run(attempt())
        self.assert_unchanged()


if __name__ == "__main__":
    unittest.main()
