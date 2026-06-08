from collections.abc import AsyncGenerator
import time
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessage, ChatSession, ChatSessionKb
from app.models.users import User
from app.models.workspaces import Workspace
from app.services.llm_service import LLMService


class ChatService:
    def __init__(self) -> None:
        self.llm_service = LLMService()

    @staticmethod
    def build_session_title(message: str) -> str:
        title = " ".join(message.strip().split())
        return title[:30] or "New Chat"

    @staticmethod
    def _parse_session_id(session_id: str | int | None) -> int | None:
        if session_id is None:
            return None
        try:
            value = int(session_id)
        except (TypeError, ValueError):
            return None
        return value if value > 0 else None

    async def _get_default_workspace(self, db: AsyncSession) -> Workspace:
        result = await db.execute(
            select(Workspace)
            .where(Workspace.status == "active")
            .order_by(Workspace.id.asc())
            .limit(1)
        )
        workspace = result.scalar_one_or_none()
        if workspace is not None:
            return workspace

        result = await db.execute(
            select(User)
            .where(User.status == "active")
            .order_by(User.id.asc())
            .limit(1)
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise RuntimeError("No active user is available for chat sessions")

        workspace = Workspace(
            name="Default Workspace",
            owner_user_id=user.id,
            status="active",
        )
        db.add(workspace)
        await db.flush()
        return workspace

    def _build_messages(
        self,
        history: list[dict[str, Any]],
        user_message: str,
    ) -> list[dict[str, Any]]:
        return [
            {
                "role": "system",
                "content": "你是一个严谨、简洁的 AI 助手。",
            },
            *history,
            {
                "role": "user",
                "content": user_message,
            },
        ]

    async def _get_history(
        self,
        db: AsyncSession,
        session_id: str | int,
    ) -> list[dict[str, str]]:
        parsed_session_id = self._parse_session_id(session_id)
        if parsed_session_id is None:
            return []

        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == parsed_session_id)
            .order_by(ChatMessage.created_at.asc())
        )
        messages = result.scalars().all()
        return [
            {
                "role": message.role,
                "content": message.content,
            }
            for message in messages
        ]

    async def _get_or_create_session(
        self,
        db: AsyncSession,
        session_id: str | int | None,
        message: str,
    ) -> ChatSession:
        parsed_session_id = self._parse_session_id(session_id)
        if parsed_session_id is not None:
            result = await db.execute(
                select(ChatSession).where(
                    ChatSession.id == parsed_session_id,
                    ChatSession.status == "active",
                )
            )
            chat_session = result.scalar_one_or_none()
            if chat_session is not None:
                return chat_session

        workspace = await self._get_default_workspace(db)
        chat_session = ChatSession(
            user_id=workspace.owner_user_id,
            workspace_id=workspace.id,
            title=self.build_session_title(message),
            status="active",
        )
        db.add(chat_session)
        await db.flush()
        return chat_session

    async def _save_message(
        self,
        db: AsyncSession,
        session_id: int,
        role: str,
        content: str,
        latency_ms: int | None = None,
    ) -> None:
        db.add(
            ChatMessage(
                session_id=session_id,
                role=role,
                content=content,
                model_name=self.llm_service.model if role == "assistant" else None,
                latency_ms=latency_ms,
            )
        )

    async def chat(
        self,
        db: AsyncSession,
        session_id: str,
        message: str,
    ) -> dict:
        chat_session = await self._get_or_create_session(db, session_id, message)
        history = await self._get_history(db, chat_session.id)
        messages = self._build_messages(history, message)
        start_time = time.perf_counter()

        answer = await self.llm_service.chat(messages)
        latency_ms = int((time.perf_counter() - start_time) * 1000)

        await self._save_message(
            db=db,
            session_id=chat_session.id,
            role="user",
            content=message,
        )
        await self._save_message(
            db=db,
            session_id=chat_session.id,
            role="assistant",
            content=answer,
            latency_ms=latency_ms,
        )
        await db.commit()

        return {
            "session_id": chat_session.id,
            "answer": answer,
        }

    async def stream_chat(
        self,
        db: AsyncSession,
        session_id: str,
        message: str,
    ) -> AsyncGenerator[str, None]:
        chat_session = await self._get_or_create_session(db, session_id, message)
        history = await self._get_history(db, chat_session.id)
        messages = self._build_messages(history, message)
        answer_chunks: list[str] = []
        start_time = time.perf_counter()

        async for chunk in self.llm_service.stream_chat(messages):
            answer_chunks.append(chunk)
            yield chunk

        full_answer = "".join(answer_chunks)
        latency_ms = int((time.perf_counter() - start_time) * 1000)

        await self._save_message(
            db=db,
            session_id=chat_session.id,
            role="user",
            content=message,
        )
        await self._save_message(
            db=db,
            session_id=chat_session.id,
            role="assistant",
            content=full_answer,
            latency_ms=latency_ms,
        )
        await db.commit()

    async def get_messages(
        self,
        db: AsyncSession,
        session_id: str | int,
    ) -> list[dict[str, str]]:
        return await self._get_history(db, session_id)

    async def delete_session(
        self,
        db: AsyncSession,
        session_id: str | int,
    ) -> bool:
        parsed_session_id = self._parse_session_id(session_id)
        if parsed_session_id is None:
            return False

        result = await db.execute(
            select(ChatSession).where(ChatSession.id == parsed_session_id)
        )
        chat_session = result.scalar_one_or_none()
        if chat_session is None:
            return False

        await db.execute(delete(ChatMessage).where(ChatMessage.session_id == parsed_session_id))
        await db.execute(delete(ChatSessionKb).where(ChatSessionKb.session_id == parsed_session_id))
        await db.execute(delete(ChatSession).where(ChatSession.id == parsed_session_id))
        await db.commit()

        return True
