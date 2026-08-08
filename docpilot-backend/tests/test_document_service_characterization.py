from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from app.core.exceptions import AppException
from app.services import document_service as document_service_module
from tests.document_service_fakes import (
    FakeDatabase,
    FakeScalarResult,
    FakeTaskService,
    FakeUploadFile,
    FakeVectorService,
    make_service,
)


class DocumentServiceCharacterizationTests(
    unittest.IsolatedAsyncioTestCase
):
    async def test_upload_rejects_an_empty_file_list(self) -> None:
        service = make_service()

        with self.assertRaises(AppException) as context:
            await service.upload_documents(
                db=FakeDatabase(),
                user_id=1,
                kb_id=2,
                files=[],
            )

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(context.exception.message, "No files uploaded")

    async def test_upload_returns_saved_records_and_schedules_each_task(
        self,
    ) -> None:
        service = make_service()
        service._get_owned_knowledge_base = AsyncMock(
            return_value=SimpleNamespace(id=7)
        )
        saved = [
            {
                "id": 10,
                "version_id": 20,
                "task_id": "task-10",
                "original_file_name": "one.txt",
                "storage_path": "one-path",
            },
            {
                "id": 11,
                "version_id": 21,
                "task_id": "task-11",
                "original_file_name": "two.txt",
                "storage_path": "two-path",
            },
        ]
        service._save_uploaded_file = AsyncMock(side_effect=saved)
        service._start_background_task = Mock()

        result = await service.upload_documents(
            db=FakeDatabase(),
            user_id=1,
            kb_id=7,
            files=[
                FakeUploadFile("one.txt", b"one"),
                FakeUploadFile("two.txt", b"two"),
            ],
        )

        self.assertEqual(result, saved)
        self.assertEqual(service._save_uploaded_file.await_count, 2)
        self.assertEqual(service._start_background_task.call_count, 2)
        service._start_background_task.assert_any_call(
            document_id=10,
            version_id=20,
            task_id="task-10",
            kb_id=7,
            filename="one.txt",
            storage_path="one-path",
        )

    async def test_save_upload_succeeds_when_redis_cache_is_unavailable(
        self,
    ) -> None:
        task_service = FakeTaskService(cache_result=False)
        service = make_service(task=task_service)
        db = FakeDatabase()

        with tempfile.TemporaryDirectory() as temp_dir:
            fake_module_file = (
                Path(temp_dir) / "app" / "services" / "document_service.py"
            )
            with patch.object(
                document_service_module,
                "__file__",
                str(fake_module_file),
            ):
                result = await service._save_uploaded_file(
                    db=db,
                    user_id=3,
                    kb_id=7,
                    file=FakeUploadFile("sample.txt", b"hello"),
                )

            self.assertTrue(Path(result["storage_path"]).is_file())

        self.assertEqual(result["parse_status"], "pending")
        self.assertEqual(result["index_status"], "not_indexed")
        self.assertEqual(db.commits, 1)
        self.assertEqual(db.rollbacks, 0)
        self.assertIn(
            "cache_task_by_id",
            [name for name, _values in task_service.calls],
        )

    async def test_permission_denial_keeps_the_existing_404_contract(
        self,
    ) -> None:
        service = make_service()
        db = FakeDatabase([FakeScalarResult(scalar=None)])

        with self.assertRaises(AppException) as context:
            await service._get_owned_knowledge_base(
                db=db,
                user_id=1,
                kb_id=999,
            )

        self.assertEqual(context.exception.status_code, 404)
        self.assertEqual(
            context.exception.message,
            "Knowledge base does not exist",
        )

    async def test_document_queries_keep_filters_and_return_shapes(
        self,
    ) -> None:
        service = make_service()
        documents = [SimpleNamespace(id=1), SimpleNamespace(id=2)]
        db = FakeDatabase(
            [
                FakeScalarResult(scalar=SimpleNamespace(id=7)),
                FakeScalarResult(scalars=documents),
                FakeScalarResult(scalar=4),
            ]
        )

        listed = await service.list_documents(db, user_id=1, kb_id=7)
        count = await service.count_chunks(db, document_id=1, kb_id=7)

        self.assertEqual(listed, documents)
        self.assertEqual(count, 4)

    async def test_delete_removes_vectors_then_soft_deletes_mysql_rows(
        self,
    ) -> None:
        vector_service = FakeVectorService()
        service = make_service(vector=vector_service)
        db = FakeDatabase(
            [
                FakeScalarResult(scalar=SimpleNamespace(id=7)),
                FakeScalarResult(scalars=["v1", "v2"]),
            ]
        )

        deleted = await service.delete_document(
            db=db,
            user_id=1,
            kb_id=7,
            document_id=10,
        )

        self.assertTrue(deleted)
        self.assertEqual(vector_service.deletions, [["v1", "v2"]])
        self.assertEqual(db.commits, 1)


if __name__ == "__main__":
    unittest.main()
