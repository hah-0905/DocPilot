from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from app.models.documents import Document, DocumentVersion
from app.services import document_service as document_service_module
from app.services.document_service import DocumentService


class FakeScalarResult:
    def __init__(
        self,
        *,
        scalar: Any = None,
        scalars: list[Any] | None = None,
    ) -> None:
        self.scalar = scalar
        self.scalar_values = scalars or []

    def scalar_one_or_none(self) -> Any:
        return self.scalar

    def scalar_one(self) -> Any:
        return self.scalar

    def scalars(self) -> FakeScalarResult:
        return self

    def all(self) -> list[Any]:
        return list(self.scalar_values)


class FakeDatabase:
    def __init__(
        self,
        results: list[FakeScalarResult] | None = None,
        *,
        document: Any = None,
        version: Any = None,
    ) -> None:
        self.results = list(results or [])
        self.document = document
        self.version = version
        self.added: list[Any] = []
        self.commits = 0
        self.rollbacks = 0
        self.flushes = 0
        self._next_id = 100

    async def execute(self, _statement: Any) -> FakeScalarResult:
        if self.results:
            return self.results.pop(0)
        return FakeScalarResult()

    def add(self, value: Any) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        self.flushes += 1
        for value in self.added:
            if getattr(value, "id", None) is None:
                value.id = self._next_id
                self._next_id += 1

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1

    async def get(self, model: type[Any], _object_id: int) -> Any:
        if model is Document:
            return self.document
        if model is DocumentVersion:
            return self.version
        return None


class FakeSessionContext:
    def __init__(self, db: FakeDatabase) -> None:
        self.db = db

    async def __aenter__(self) -> FakeDatabase:
        return self.db

    async def __aexit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _traceback: Any,
    ) -> None:
        return None


class FakeTaskService:
    def __init__(self, *, cache_result: bool = True) -> None:
        self.cache_result = cache_result
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def create_task(self, _db: Any = None, **kwargs: Any) -> Any:
        self.calls.append(("create_task", kwargs))
        return SimpleNamespace(task_id="task-1")

    async def cache_task_by_id(
        self,
        task_id: str,
        *,
        force_latest: bool,
    ) -> bool:
        self.calls.append(
            (
                "cache_task_by_id",
                {"task_id": task_id, "force_latest": force_latest},
            )
        )
        return self.cache_result

    async def mark_running(self, task_id: str, **kwargs: Any) -> bool:
        self.calls.append(("mark_running", {"task_id": task_id, **kwargs}))
        return True

    async def update_progress(self, task_id: str, **kwargs: Any) -> bool:
        self.calls.append(("update_progress", {"task_id": task_id, **kwargs}))
        return True

    async def mark_success(self, task_id: str, **kwargs: Any) -> bool:
        self.calls.append(("mark_success", {"task_id": task_id, **kwargs}))
        return True

    async def mark_failed(self, task_id: str, **kwargs: Any) -> bool:
        self.calls.append(("mark_failed", {"task_id": task_id, **kwargs}))
        return True


class FakeLLMService:
    embedding_model = "fake-embedding"

    def __init__(self, embedding: list[float] | None = None) -> None:
        self.embedding = [0.1, 0.2] if embedding is None else embedding
        self.calls: list[str] = []

    async def embed_text(self, text: str) -> list[float]:
        self.calls.append(text)
        return self.embedding


class FakeVectorService:
    vector_store_type = "fake"
    vector_collection = "fake_chunks"

    def __init__(
        self,
        *,
        fail_upsert: bool = False,
        fail_on_upsert: int | None = None,
    ) -> None:
        self.fail_upsert = fail_upsert
        self.fail_on_upsert = fail_on_upsert
        self.upserts: list[dict[str, Any]] = []
        self.deletions: list[list[str]] = []

    async def upsert_chunk_vector(self, **kwargs: Any) -> None:
        call_number = len(self.upserts) + 1
        if self.fail_upsert or call_number == self.fail_on_upsert:
            raise RuntimeError("vector unavailable")
        self.upserts.append(kwargs)

    async def delete_vectors(self, vector_ids: list[str]) -> None:
        self.deletions.append(list(vector_ids))


class FakeUploadFile:
    def __init__(
        self,
        filename: str,
        content: bytes,
        content_type: str = "text/plain",
    ) -> None:
        self.filename = filename
        self.content_type = content_type
        self._content = content

    async def read(self) -> bytes:
        return self._content


def make_service(
    *,
    llm: FakeLLMService | None = None,
    vector: FakeVectorService | None = None,
    task: FakeTaskService | None = None,
) -> DocumentService:
    llm = llm or FakeLLMService()
    vector = vector or FakeVectorService()
    task = task or FakeTaskService()
    with (
        patch.object(document_service_module, "LLMService", return_value=llm),
        patch.object(
            document_service_module,
            "VectorService",
            return_value=vector,
        ),
        patch.object(
            document_service_module,
            "DocumentTaskService",
            return_value=task,
        ),
    ):
        return DocumentService()
