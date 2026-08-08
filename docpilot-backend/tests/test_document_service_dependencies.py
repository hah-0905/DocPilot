from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services import document_service as document_service_module
from app.services.document_service import DocumentService
from app.services.documents.document_query_service import DocumentQueryService
from app.services.documents.document_storage import DocumentStorage


class DocumentServiceDependencyTests(unittest.TestCase):
    def test_explicit_dependencies_skip_default_external_constructors(
        self,
    ) -> None:
        llm_service = object()
        vector_service = object()
        task_service = object()
        storage = DocumentStorage(upload_root=Path("unused"))
        query_service = DocumentQueryService()

        with (
            patch.object(
                document_service_module,
                "LLMService",
                side_effect=AssertionError("default LLM constructed"),
            ),
            patch.object(
                document_service_module,
                "VectorService",
                side_effect=AssertionError("default vector constructed"),
            ),
            patch.object(
                document_service_module,
                "DocumentTaskService",
                side_effect=AssertionError("default task service constructed"),
            ),
        ):
            service = DocumentService(
                llm_service=llm_service,
                vector_service=vector_service,
                task_service=task_service,
                storage=storage,
                query_service=query_service,
            )

        self.assertIs(service.llm_service, llm_service)
        self.assertIs(service.vector_service, vector_service)
        self.assertIs(service.task_service, task_service)
        self.assertIs(service.storage, storage)
        self.assertIs(service.query_service, query_service)
        self.assertIs(
            service.processing_service.chunk_indexer.llm_service,
            llm_service,
        )
        self.assertIs(
            service.processing_service.chunk_indexer.vector_service,
            vector_service,
        )

    def test_storage_can_be_replaced_with_a_temporary_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = DocumentStorage(upload_root=Path(temp_dir))
            stored_path = storage.save(
                kb_id=7,
                filename="../unsafe.txt",
                file_sha256="abc",
                file_bytes=b"payload",
            )

            self.assertEqual(stored_path.parent, Path(temp_dir) / "7")
            self.assertEqual(stored_path.name, "abc_unsafe.txt")
            self.assertEqual(
                storage.read(str(stored_path), "unsafe.txt"),
                b"payload",
            )

            storage.delete(stored_path)
            self.assertFalse(stored_path.exists())


if __name__ == "__main__":
    unittest.main()
