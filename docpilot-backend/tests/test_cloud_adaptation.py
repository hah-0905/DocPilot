import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

os.environ.setdefault("DATABASE_URL", "mysql+aiomysql://user:pass@mysql:3306/docpilot")
os.environ.setdefault("REDIS_URL", "redis://redis:6379/0")
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("OPENAI_BASE_URL", "https://api.openai.com/v1")
os.environ.setdefault("MODEL_NAME", "test-model")
os.environ.setdefault("EMBEDDING_MODEL", "test-embedding-model")

from fastapi import HTTPException
from pydantic import ValidationError

from app.api.users import update_user_info_legacy
from app.core.storage import path_in_directory
from app.schemas.users import PasswordChangeRequest, UserUpdateRequest
from app.services import users_service
from app.utils import security


class CloudAdaptationTests(unittest.TestCase):
    def test_empty_profile_update_is_rejected(self):
        with self.assertRaises(ValidationError):
            UserUpdateRequest()

    def test_legacy_update_rejects_another_user(self):
        async def run_test():
            with self.assertRaises(HTTPException) as context:
                await update_user_info_legacy(
                    user_id=2,
                    request=UserUpdateRequest(display_name="New name"),
                    current_user=SimpleNamespace(id=1),
                    db=AsyncMock(),
                )
            self.assertEqual(context.exception.status_code, 403)

        asyncio.run(run_test())

    def test_missing_bearer_token_is_unauthorized(self):
        async def run_test():
            with self.assertRaises(HTTPException) as context:
                await users_service.get_current_user(credentials=None, db=AsyncMock())
            self.assertEqual(context.exception.status_code, 401)

        asyncio.run(run_test())

    def test_invalid_redis_user_id_is_unauthorized(self):
        async def run_test():
            with patch.object(
                users_service.redis_client,
                "get",
                new=AsyncMock(return_value="not-an-integer"),
            ), patch.object(
                users_service.redis_client,
                "expire",
                new=AsyncMock(return_value=True),
            ):
                with self.assertRaises(HTTPException) as context:
                    await users_service.get_current_user(
                        credentials=SimpleNamespace(credentials="opaque-token"),
                        db=AsyncMock(),
                    )
                self.assertEqual(context.exception.status_code, 401)

        asyncio.run(run_test())

    def test_password_change_rehashes_password(self):
        async def run_test():
            original_hash = security.get_hash_password("old-password")
            user = SimpleNamespace(password_hash=original_hash)
            db = AsyncMock()
            await users_service.change_password(
                user,
                PasswordChangeRequest(
                    current_password="old-password",
                    new_password="new-password",
                ),
                db,
            )
            self.assertNotEqual(user.password_hash, original_hash)
            self.assertTrue(security.verify_password("new-password", user.password_hash))
            db.commit.assert_awaited_once()

        asyncio.run(run_test())

    def test_storage_path_cannot_escape_data_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "uploads"
            root.mkdir()
            self.assertEqual(
                path_in_directory(root, root / "kb" / "file.txt"),
                (root / "kb" / "file.txt").resolve(),
            )
            with self.assertRaises(ValueError):
                path_in_directory(root, root / ".." / "outside.txt")

    def test_report_export_list_awaits_both_queries(self):
        source = Path("app/api/report.py").read_text(encoding="utf-8")
        route_source = source[source.index("async def list_report_exports"):]
        self.assertIn("task_result = await db.execute(", route_source)
        self.assertIn("result = await db.execute(", route_source)


if __name__ == "__main__":
    unittest.main()
