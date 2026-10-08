"""API security regressions using real SQLite SQL and an isolated token store."""

import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.settings import router as settings_router
from app.api.users import router as users_router
from app.core import redis as redis_module
from app.core.exception_handlers import register_exception_handlers
from app.db.session import get_db
from app.models.users import User
from app.schemas.users import PasswordChangeRequest, UserInfoUpdate
from app.services import users_service as users
from app.utils import security


class MemoryTokenStore:
    def __init__(self):
        self.values = {}
        self.renewed = []

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, value, *, ex):
        self.values[key] = value

    async def expire(self, key, seconds):
        self.renewed.append(key)

    async def delete(self, key):
        self.values.pop(key, None)


class SQLiteAsyncSession:
    """Async interface over real SQL; no external database or SQL-filter fake."""

    def __init__(self, engine):
        self.session = Session(engine, expire_on_commit=False)

    async def execute(self, statement):
        return self.session.execute(statement)

    async def get(self, model, key):
        return self.session.get(model, key)

    async def commit(self):
        self.session.commit()

    async def rollback(self):
        self.session.rollback()

    async def refresh(self, instance):
        self.session.refresh(instance)


class UserAccountSecurityTests(unittest.TestCase):
    old_password = "old-password-123"
    new_password = "new-password-456"

    @classmethod
    def setUpClass(cls):
        cls.old_hash = security.get_hash_password(cls.old_password)

    def setUp(self):
        self.engine = create_engine(
            "sqlite://", poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        self.addCleanup(self.engine.dispose)
        # Keep the production ORM and statements; SQLite DDL avoids MySQL-only defaults.
        with self.engine.begin() as connection:
            connection.exec_driver_sql("""
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY, username VARCHAR(64) NOT NULL UNIQUE,
                    email VARCHAR(128) NOT NULL UNIQUE, password_hash VARCHAR(255) NOT NULL,
                    display_name VARCHAR(128), avatar_url VARCHAR(512),
                    status VARCHAR(32) NOT NULL DEFAULT 'active', last_login_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP, deleted_at DATETIME
                )
            """)
        with Session(self.engine) as db:
            db.add_all([
                User(id=1, username="alice", email="alice@example.com", password_hash=self.old_hash, status="active"),
                User(id=2, username="bob", email="bob@example.com", password_hash=self.old_hash, status="active"),
            ])
            db.commit()

        self.tokens = MemoryTokenStore()
        token_patch = patch.object(redis_module, "_redis_client", self.tokens)
        token_patch.start()
        self.addCleanup(token_patch.stop)
        for token, user_id in [("alice-one", 1), ("alice-two", 1), ("bob-one", 2)]:
            self.tokens.values[f"login:token:{token}"] = json.dumps({
                "user_id": user_id,
                "credential_version": users._credential_version(self.old_hash),
            })

        app = FastAPI()
        app.include_router(users_router)
        app.include_router(settings_router)
        register_exception_handlers(app)

        async def isolated_db():
            db = SQLiteAsyncSession(self.engine)
            try:
                yield db
            finally:
                db.session.close()

        app.dependency_overrides[get_db] = isolated_db

        @app.get("/test/whoami")
        async def whoami(user: User = Depends(users.get_current_user)):
            return {"id": user.id}

        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def headers(self, token="alice-one"):
        return {"Authorization": f"Bearer {token}"}

    def profile_request(self, route, user_id, payload, token="alice-one"):
        method = "post" if route == "user" else "put"
        path = f"/api/user/update/{user_id}" if route == "user" else f"/api/settings/userInfo/{user_id}"
        return self.client.request(method, path, json=payload, headers=self.headers(token))

    def password_request(self, **overrides):
        return self.client.post("/api/user/change-password", headers=self.headers(), json={
            "current_password": self.old_password,
            "new_password": self.new_password,
            **overrides,
        })

    def assert_password_unchanged(self):
        with Session(self.engine) as db:
            self.assertEqual(db.get(User, 1).password_hash, self.old_hash)
            self.assertEqual(db.get(User, 2).password_hash, self.old_hash)

    def test_anonymous_profile_update_is_rejected(self):
        for method, path in [("post", "/api/user/update/1"), ("put", "/api/settings/userInfo/1")]:
            with self.subTest(path=path):
                response = self.client.request(method, path, json={"username": "changed"})
                self.assertIn(response.status_code, {401, 403})
        self.assert_password_unchanged()

    def test_invalid_token_is_rejected(self):
        response = self.profile_request("user", 1, {"username": "changed"}, token="unknown")
        self.assertEqual(response.status_code, 401)
        self.assert_password_unchanged()

    def test_both_profile_routes_reject_other_users(self):
        for route in ("user", "settings"):
            with self.subTest(route=route):
                response = self.profile_request(route, 2, {"username": "changed"})
                self.assertEqual(response.status_code, 403)
        with Session(self.engine) as db:
            self.assertEqual(db.get(User, 2).username, "bob")

    def test_both_profile_routes_reject_password_fields(self):
        for route in ("user", "settings"):
            for field in ("password", "password_hash"):
                with self.subTest(route=route, field=field):
                    response = self.profile_request(route, 1, {"username": "changed", field: self.new_password})
                    self.assertEqual(response.status_code, 422)
        self.assert_password_unchanged()

    def test_profile_updates_return_only_public_fields(self):
        for route, username in [("user", "alice-new"), ("settings", "alice-next")]:
            with self.subTest(route=route):
                response = self.profile_request(route, 1, {"username": username, "display_name": "Alice"})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["username"], username)
                self.assertEqual(response.json()["display_name"], "Alice")
                self.assertNotIn("password_hash", response.json())
                self.assertNotIn("auth_action_tokens", response.json())
        self.assert_password_unchanged()

    def test_profile_duplicate_email_is_safe_conflict(self):
        response = self.profile_request("user", 1, {"email": "bob@example.com"})
        self.assertEqual(response.status_code, 409)
        self.assertNotIn("UPDATE", response.text)
        with Session(self.engine) as db:
            self.assertEqual(db.get(User, 1).email, "alice@example.com")

    def test_profile_rejects_empty_null_and_privilege_updates(self):
        for payload in ({}, {"username": None}, {"email": None}, {"role": "admin"}):
            with self.subTest(payload=payload):
                self.assertEqual(self.profile_request("user", 1, payload).status_code, 422)

    def test_service_also_enforces_ownership(self):
        db = SQLiteAsyncSession(self.engine)
        self.addCleanup(db.session.close)
        with self.assertRaises(HTTPException) as error:
            asyncio.run(users.update_user_info(
                2, UserInfoUpdate(username="changed"), db,
                current_user=SimpleNamespace(id=1),
            ))
        self.assertEqual(error.exception.status_code, 403)
        self.assert_password_unchanged()

    def test_password_change_requires_authentication(self):
        response = self.client.post("/api/user/change-password", json={
            "current_password": self.old_password, "new_password": self.new_password,
        })
        self.assertIn(response.status_code, {401, 403})
        self.assert_password_unchanged()

    def test_wrong_old_password_preserves_sessions_and_credentials(self):
        self.assertEqual(self.password_request(current_password="wrong-password").status_code, 400)
        self.assert_password_unchanged()
        self.assertEqual(self.client.get("/test/whoami", headers=self.headers()).status_code, 200)

    def test_identical_new_password_is_rejected(self):
        self.assertEqual(self.password_request(new_password=self.old_password).status_code, 422)
        self.assert_password_unchanged()

    def test_new_password_validates_bcrypt_byte_limit(self):
        for password in ("short", "x" * 73, "密" * 25):
            with self.subTest(length=len(password)):
                self.assertEqual(self.password_request(new_password=password).status_code, 422)
        accepted = PasswordChangeRequest(current_password=self.old_password, new_password="密" * 24)
        self.assertEqual(len(accepted.new_password.encode("utf-8")), 72)
        self.assert_password_unchanged()

    def test_password_change_revokes_all_own_tokens_and_allows_new_login(self):
        response = self.password_request()
        self.assertEqual(response.status_code, 200, response.text)
        with Session(self.engine) as db:
            self.assertTrue(security.verify_password(self.new_password, db.get(User, 1).password_hash))
            self.assertEqual(db.get(User, 2).password_hash, self.old_hash)
        for token in ("alice-one", "alice-two"):
            self.assertEqual(self.client.get("/test/whoami", headers=self.headers(token)).status_code, 401)
        self.assertEqual(self.client.get("/test/whoami", headers=self.headers("bob-one")).status_code, 200)
        self.assertEqual(self.client.post("/api/user/login", json={"username": "alice", "password": self.old_password}).status_code, 401)
        login = self.client.post("/api/user/login", json={"username": "alice", "password": self.new_password})
        self.assertEqual(login.status_code, 200, login.text)
        token = login.json()["data"]["token"]
        self.assertEqual(self.client.get("/test/whoami", headers=self.headers(token)).status_code, 200)

    def test_login_issues_password_bound_token_without_raw_hash(self):
        response = self.client.post("/api/user/login", json={"username": "alice", "password": self.old_password})
        self.assertEqual(response.status_code, 200, response.text)
        token = response.json()["data"]["token"]
        stored = self.tokens.values[f"login:token:{token}"]
        self.assertNotIn(self.old_hash, stored)
        self.assertEqual(json.loads(stored)["user_id"], 1)
        self.assertEqual(self.client.get("/test/whoami", headers=self.headers(token)).status_code, 200)

    def test_legacy_and_malformed_tokens_fail_closed_without_renewal(self):
        for value in ("1", "not-json", "null", "{}", '{"user_id": true, "credential_version": "x"}',
                      '{"user_id": 1, "credential_version": 2}', '{"user_id": 1, "credential_version": "错"}'):
            with self.subTest(value=value):
                self.tokens.values["login:token:legacy"] = value
                response = self.client.get("/test/whoami", headers=self.headers("legacy"))
                self.assertEqual(response.status_code, 401)
        self.assertNotIn("login:token:legacy", self.tokens.renewed)

    def test_concurrent_stale_password_change_cannot_overwrite_new_password(self):
        first = SQLiteAsyncSession(self.engine)
        second = SQLiteAsyncSession(self.engine)
        self.addCleanup(first.session.close)
        self.addCleanup(second.session.close)
        first_user = first.session.get(User, 1)
        stale_user = second.session.get(User, 1)
        asyncio.run(users.change_password(
            PasswordChangeRequest(current_password=self.old_password, new_password=self.new_password),
            first, current_user=first_user,
        ))
        with self.assertRaises(HTTPException) as error:
            asyncio.run(users.change_password(
                PasswordChangeRequest(current_password=self.old_password, new_password="third-password-789"),
                second, current_user=stale_user,
            ))
        self.assertEqual(error.exception.status_code, 409)
        with Session(self.engine) as db:
            self.assertTrue(security.verify_password(self.new_password, db.get(User, 1).password_hash))

    def test_failed_password_commit_rolls_back_and_preserves_sessions(self):
        db = SQLiteAsyncSession(self.engine)
        self.addCleanup(db.session.close)
        user = db.session.get(User, 1)
        with patch.object(db, "commit", new=AsyncMock(side_effect=RuntimeError("commit failed"))):
            with self.assertRaises(RuntimeError):
                asyncio.run(users.change_password(
                    PasswordChangeRequest(current_password=self.old_password, new_password=self.new_password),
                    db, current_user=user,
                ))
        self.assert_password_unchanged()
        self.assertEqual(self.client.get("/test/whoami", headers=self.headers()).status_code, 200)


if __name__ == "__main__":
    unittest.main()
