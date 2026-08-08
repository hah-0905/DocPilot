from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.services import document_service as document_service_module
from tests.document_service_fakes import (
    FakeDatabase,
    FakeLLMService,
    FakeSessionContext,
    FakeTaskService,
    FakeVectorService,
    make_service,
)


class DocumentProcessingCharacterizationTests(
    unittest.IsolatedAsyncioTestCase
):
    def make_case(
        self,
        *,
        llm: FakeLLMService | None = None,
        vector: FakeVectorService | None = None,
    ) -> tuple[
        object,
        FakeDatabase,
        SimpleNamespace,
        SimpleNamespace,
        FakeTaskService,
        FakeVectorService,
    ]:
        task_service = FakeTaskService()
        vector_service = vector or FakeVectorService()
        service = make_service(
            llm=llm,
            vector=vector_service,
            task=task_service,
        )
        document = SimpleNamespace(
            id=10,
            sha256="file-hash",
            parse_status="pending",
            index_status="not_indexed",
        )
        version = SimpleNamespace(
            id=20,
            status="pending",
            error_message=None,
            char_count=None,
            token_count=None,
        )
        db = FakeDatabase(document=document, version=version)
        return (
            service,
            db,
            document,
            version,
            task_service,
            vector_service,
        )

    async def run_processing(
        self,
        *,
        service: object,
        db: FakeDatabase,
        parser: Mock,
        chunks: list[str],
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "source.txt"
            source_path.write_bytes(b"source")
            with (
                patch(
                    "app.db.session.AsyncSessional",
                    return_value=FakeSessionContext(db),
                ),
                patch.object(
                    document_service_module,
                    "parse_document",
                    new=parser,
                ),
                patch.object(
                    document_service_module,
                    "split_text",
                    return_value=chunks,
                ),
            ):
                await service._process_document_in_background(
                    document_id=10,
                    version_id=20,
                    task_id="task-1",
                    kb_id=7,
                    filename="source.txt",
                    storage_path=str(source_path),
                )

    async def test_processing_success_updates_mysql_vectors_and_task(
        self,
    ) -> None:
        service, db, document, version, task, vector = self.make_case()
        await self.run_processing(
            service=service,
            db=db,
            parser=Mock(return_value="parsed text"),
            chunks=["chunk one", "chunk two"],
        )

        self.assertEqual(document.parse_status, "success")
        self.assertEqual(document.index_status, "indexed")
        self.assertEqual(version.status, "success")
        self.assertEqual(len(vector.upserts), 2)
        self.assertEqual(db.commits, 3)
        self.assertIn("mark_success", [name for name, _values in task.calls])

    async def test_processing_parse_failure_persists_failure_state(
        self,
    ) -> None:
        service, db, document, version, task, _vector = self.make_case()
        await self.run_processing(
            service=service,
            db=db,
            parser=Mock(side_effect=ValueError("parse failed")),
            chunks=[],
        )

        self.assertEqual(document.parse_status, "failed")
        self.assertEqual(document.index_status, "not_indexed")
        self.assertEqual(version.status, "failed")
        failed = [values for name, values in task.calls if name == "mark_failed"]
        self.assertEqual(failed[0]["error_code"], "DOCUMENT_PARSE_FAILED")
        self.assertEqual(db.rollbacks, 1)

    async def test_embedding_failure_does_not_leave_vectors(self) -> None:
        service, db, document, _version, task, vector = self.make_case(
            llm=FakeLLMService(embedding=[]),
        )
        await self.run_processing(
            service=service,
            db=db,
            parser=Mock(return_value="parsed text"),
            chunks=["chunk"],
        )

        self.assertEqual(vector.upserts, [])
        self.assertEqual(vector.deletions, [])
        self.assertEqual(document.index_status, "failed")
        failed = [values for name, values in task.calls if name == "mark_failed"]
        self.assertEqual(failed[0]["error_code"], "EMBEDDING_FAILED")

    async def test_vector_failure_is_reported_without_false_cleanup(
        self,
    ) -> None:
        service, db, _document, _version, task, vector = self.make_case(
            vector=FakeVectorService(fail_upsert=True),
        )
        await self.run_processing(
            service=service,
            db=db,
            parser=Mock(return_value="parsed text"),
            chunks=["chunk"],
        )

        self.assertEqual(vector.deletions, [])
        failed = [values for name, values in task.calls if name == "mark_failed"]
        self.assertEqual(failed[0]["error_code"], "VECTOR_UPSERT_FAILED")


    async def test_partial_vector_failure_cleans_up_inserted_vectors(
        self,
    ) -> None:
        service, db, _document, _version, task, vector = self.make_case(
            vector=FakeVectorService(fail_on_upsert=2),
        )
        await self.run_processing(
            service=service,
            db=db,
            parser=Mock(return_value="parsed text"),
            chunks=["first chunk", "second chunk"],
        )

        self.assertEqual(len(vector.upserts), 1)
        self.assertEqual(vector.deletions, [["100"]])
        failed = [
            values
            for name, values in task.calls
            if name == "mark_failed"
        ]
        self.assertEqual(failed[0]["error_code"], "VECTOR_UPSERT_FAILED")

if __name__ == "__main__":
    unittest.main()
