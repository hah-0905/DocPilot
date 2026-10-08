"""Background writes must respect deletion and the current document version."""

import asyncio
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock

from sqlalchemy import event, func, select
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Session

from app.models.documents import Document, DocumentChunk, DocumentVersion
from tests import test_report_and_delete_security as resources
from tests.document_service_fakes import FakeLLMService, FakeTaskService, FakeVectorService, make_service
from tests.security_sqlite import SecuritySession


class DocumentLifecycleSecurityTests(resources.ResourceSecurityFixture):
    def setUp(self):
        super().setUp()
        self.llm = FakeLLMService()
        self.vector = FakeVectorService()
        self.task = FakeTaskService()
        self.service = make_service(llm=self.llm, vector=self.vector, task=self.task)
        self.processing = self.service.processing_service
        self.processing.session_factory = lambda: SecuritySession(self.engine)
        self.processing.storage = SimpleNamespace(read=Mock(return_value=b"source"))
        self.processing.parser = Mock(return_value="parsed text")
        self.processing.splitter = Mock(return_value=["new chunk"])

    def process(self, **overrides):
        asyncio.run(self.processing.process_document(**{
            "document_id": 11, "version_id": 110, "task_id": "task-test",
            "kb_id": 101, "filename": "test.txt", "storage_path": "unused", **overrides,
        }))

    def mark_deleted(self):
        with Session(self.engine) as db:
            document = db.get(Document, 11)
            document.enabled = False
            document.deleted_at = datetime(2026, 10, 8)
            db.get(DocumentVersion, 110).status = "deleted"
            db.commit()

    def assert_cancelled_without_indexing(self):
        self.assertEqual(self.llm.calls, [])
        self.assertEqual(self.vector.upserts, [])
        self.assertIn("mark_cancelled", [name for name, _ in self.task.calls])
        self.assertNotIn("mark_success", [name for name, _ in self.task.calls])
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(DocumentChunk)), 2)

    def test_deleted_document_never_parses_or_indexes(self):
        self.mark_deleted()
        self.process()
        self.processing.storage.read.assert_not_called()
        self.assert_cancelled_without_indexing()
        with Session(self.engine) as db:
            self.assertEqual(db.get(DocumentVersion, 110).status, "deleted")

    def test_deletion_during_parsing_cannot_be_overwritten(self):
        def parse(**_kwargs):
            self.mark_deleted()
            return "parsed text"
        self.processing.parser.side_effect = parse
        self.process()
        self.assert_cancelled_without_indexing()
        with Session(self.engine) as db:
            self.assertFalse(db.get(Document, 11).enabled)
            self.assertEqual(db.get(DocumentVersion, 110).status, "deleted")
            self.assertIsNone(db.get(DocumentVersion, 110).char_count)

    def test_deletion_before_vector_writes_cancels_processing(self):
        original_progress = self.task.update_progress

        async def progress(task_id, **kwargs):
            if kwargs["stage"] == "embedding":
                self.mark_deleted()
            return await original_progress(task_id, **kwargs)

        self.task.update_progress = progress
        self.process()
        self.assert_cancelled_without_indexing()
        with Session(self.engine) as db:
            self.assertEqual(db.get(DocumentVersion, 110).status, "deleted")

    def test_new_version_during_parsing_cancels_old_task(self):
        def parse(**_kwargs):
            with Session(self.engine) as db:
                db.get(Document, 11).current_version_id = 111
                db.commit()
            return "parsed text"
        self.processing.parser.side_effect = parse
        self.process()
        self.assert_cancelled_without_indexing()
        with Session(self.engine) as db:
            self.assertIsNone(db.get(DocumentVersion, 110).char_count)
            self.assertEqual(db.get(DocumentVersion, 111).status, "success")

    def test_mismatched_knowledge_base_or_document_version_never_mutates(self):
        for overrides in ({"kb_id": 102}, {"version_id": 220}):
            with self.subTest(overrides=overrides):
                self.process(**overrides)
                self.assert_cancelled_without_indexing()
        with Session(self.engine) as db:
            self.assertEqual(db.get(DocumentVersion, 220).status, "success")

    def test_failure_cleanup_does_not_overwrite_deleted_version(self):
        def parse(**_kwargs):
            self.mark_deleted()
            raise ValueError("parser failed after deletion")
        self.processing.parser.side_effect = parse
        self.process()
        self.assertEqual(self.vector.upserts, [])
        with Session(self.engine) as db:
            self.assertFalse(db.get(Document, 11).enabled)
            self.assertEqual(db.get(DocumentVersion, 110).status, "deleted")
            self.assertIsNone(db.get(DocumentVersion, 110).error_message)

    def test_successful_indexing_then_deletion_removes_new_vectors(self):
        self.process()
        self.assertEqual(len(self.vector.upserts), 1)
        vector_id = self.vector.upserts[0]["vector_id"]

        async def delete():
            async with SecuritySession(self.engine) as db:
                return await self.service.delete_document(db, user_id=1, kb_id=101, document_id=11)

        self.assertTrue(asyncio.run(delete()))
        self.assertIn(vector_id, self.vector.deletions[0])
        self.assertIn("v11", self.vector.deletions[0])
        with Session(self.engine) as db:
            self.assertTrue(all(not chunk.enabled for chunk in db.scalars(select(DocumentChunk).where(DocumentChunk.document_id == 11))))

    def test_background_locks_document_then_version_and_holds_transaction_through_vectors(self):
        db = SecuritySession(self.engine)
        self.addCleanup(db.session.close)
        locking_reads = []

        def capture(state):
            if state.is_select:
                sql = str(state.statement.compile(dialect=mysql.dialect()))
                if "FOR UPDATE" in sql:
                    locking_reads.append((sql, state.execution_options.get("populate_existing")))

        event.listen(db.session, "do_orm_execute", capture)
        self.processing.session_factory = lambda: db
        original_upsert = self.vector.upsert_chunk_vector

        async def upsert(**kwargs):
            self.assertTrue(db.session.in_transaction())
            self.assertIn("FROM documents", locking_reads[-2][0])
            self.assertIn("FROM document_versions", locking_reads[-1][0])
            return await original_upsert(**kwargs)

        self.vector.upsert_chunk_vector = upsert
        self.process()
        self.assertEqual(len(locking_reads), 6)
        self.assertTrue(all(populate_existing for _sql, populate_existing in locking_reads))
        self.assertIn("mark_success", [name for name, _ in self.task.calls])


if __name__ == "__main__":
    import unittest
    unittest.main()
