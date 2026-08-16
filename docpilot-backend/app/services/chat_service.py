from collections.abc import AsyncGenerator
import time
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exception_handlers import AppException
from app.models.chat import ChatMessage, ChatSession, ChatSessionKb
from app.models.kb import KnowledgeBase
from app.models.users import User
from app.models.workspaces import Workspace
from app.services.llm_service import LLMService
from app.services.rag_service import RagService

from app.services.workspace_settings_service import (
    workspace_settings_service,
)


class ChatService:
    def __init__(self) -> None:
        self.llm_service = LLMService()
        self.rag_service = RagService()

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

    async def _get_default_workspace(
            self,
            db: AsyncSession,
            current_user: User,
    ) -> Workspace:
        result = await db.execute(
            select(Workspace)
            .where(Workspace.status == "active",
                   Workspace.owner_user_id == current_user.id)
            .order_by(Workspace.id.asc())
            .limit(1)
        )
        workspace = result.scalar_one_or_none()
        if workspace is not None:
            return workspace

        workspace = Workspace(
            name="Default Workspace",
            owner_user_id=current_user.id,
            status="active",
        )
        db.add(workspace)
        await db.flush()
        return workspace

    async def _ensure_owned_knowledge_base(
        self,
        db: AsyncSession,
        current_user: User,
        kb_id: int | None,
    ) -> None:
        if kb_id is None:
            return

        result = await db.execute(
            select(KnowledgeBase)
            .join(Workspace, Workspace.id == KnowledgeBase.workspace_id)
            .where(
                KnowledgeBase.id == kb_id,
                KnowledgeBase.status == "active",
                Workspace.status == "active",
                Workspace.owner_user_id == current_user.id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise AppException(
                message="知识库不存在或无权访问",
                code=404,
                status_code=404,
            )

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

    @staticmethod
    def _build_user_prompt(message: str, used_chunks: list[dict[str, Any]]) -> str:
        if not used_chunks:
            return message

        context_text = "\n\n".join(
            [
                f"[来源 {idx + 1}]\n{chunk['content']}"
                for idx, chunk in enumerate(used_chunks)
            ]
        )
        return f"""请基于以下知识库内容回答用户问题。

知识库内容：
{context_text}

用户问题：
{message}""".strip()

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
        current_user: User,
        session_id: str | int | None,
        message: str,
    ) -> ChatSession:
        parsed_session_id = self._parse_session_id(session_id)
        if parsed_session_id is not None:
            result = await db.execute(
                select(ChatSession).where(
                    ChatSession.id == parsed_session_id,
                    ChatSession.status == "active",
                    ChatSession.user_id == current_user.id
                )
            )
            chat_session = result.scalar_one_or_none()
            if chat_session is not None:
                return chat_session
            raise AppException(
                message="会话不存在或无权访问",
                code=404,
                status_code=404,
            )

        workspace = await self._get_default_workspace(db, current_user)
        chat_session = ChatSession(
            user_id=current_user.id,
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
        chunks: list[dict] | None = None,
        model_name: str | None = None,
    ) -> None:
        db.add(
            ChatMessage(
                session_id=session_id,
                role=role,
                content=content,
                model_name=model_name if role == "assistant" else None,
                latency_ms=latency_ms,
                metadata_={"used_chunks": chunks or []
                           } if chunks is not None else None,
            )
        )

    async def get_users_by_id(
        self,
        db: AsyncSession,
        current_user: User,
    ) -> User | None:
        result = await db.execute(
            select(User)
            .where(User.id == current_user.id)
        )
        return result.scalar_one_or_none()

    async def chat(
        self,
        db: AsyncSession,
        current_user: User,
        session_id: str,
        message: str,
        kb_id: int | None = None,
    ) -> dict:
        user = current_user
        if not user:
            raise AppException(
                message="用户不存在",
                code=404,
                status_code=404
            )

        # 1. 获取历史消息
        chat_session = await self._get_or_create_session(db, user, session_id, message)
        history = await self._get_history(db, chat_session.id)
        await self._ensure_owned_knowledge_base(db, user, kb_id)

        model_settings = await workspace_settings_service.get_model_settings(
            db=db,
            workspace_id=chat_session.workspace_id,
        )

        # 2. 检索相关 chunks
        retrieved_chunks = []
        if kb_id:
            retrieved_chunks = await self.rag_service.search(
                db,
                kb_id=kb_id,
                query=message,
                top_k=5,
            )

        used_chunks = [
            {
                "chunk_id": str(chunk.get("chunk_id") or chunk.get("id") or ""),
                "document_id": str(chunk.get("document_id") or ""),
                "content": chunk.get("content") or "",
                "metadata": chunk.get("metadata") or {},
                "score": chunk.get("score"),
            }
            for chunk in retrieved_chunks
        ]

        # 3. 构造用户 prompt。只有命中 chunks 时才注入 RAG 上下文。
        user_prompt = self._build_user_prompt(message, used_chunks)

        # 4. 构造 LLM 消息
        messages = self._build_messages(history, user_prompt)
        start_time = time.perf_counter()

        # 5. 调用大模型
        answer = await self.llm_service.chat(
            messages=messages,
            model=model_settings.model_key,
            temperature=float(model_settings.temperature),
            max_tokens=model_settings.max_tokens,
        )
        latency_ms = int((time.perf_counter() - start_time) * 1000)

        # 6. 保存用户消息
        await self._save_message(
            db=db,
            session_id=chat_session.id,
            role="user",
            content=message,
        )

        # 7. 保存 assistant 消息，并保存 chunks
        await self._save_message(
            db=db,
            session_id=chat_session.id,
            role="assistant",
            content=answer,
            latency_ms=latency_ms,
            chunks=used_chunks,
            model_name=model_settings.model_key,
        )
        await db.commit()

        # 8. 返回给前端
        return {
            "session_id": chat_session.id,
            "answer": answer,
            "used_chunks": used_chunks,
        }

    async def stream_chat(
        self,
        db: AsyncSession,
        current_user: User,
        session_id: str,
        message: str,
        kb_id: int | None = None,
    ) -> AsyncGenerator[Any, None]:
        user = current_user
        if not user:
            raise AppException(
                message="用户不存在",
                code=404,
                status_code=404
            )

        chat_session = await self._get_or_create_session(db, user, session_id, message)
        history = await self._get_history(db, chat_session.id)
        await self._ensure_owned_knowledge_base(db, user, kb_id)

        model_settings = await workspace_settings_service.get_model_settings(
            db=db,
            workspace_id=chat_session.workspace_id,
        )

        retrieved_chunks = []
        if kb_id:
            retrieved_chunks = await self.rag_service.search(
                db,
                kb_id=kb_id,
                query=message,
                top_k=5,
            )

        used_chunks = [
            {
                "chunk_id": str(chunk.get("chunk_id") or chunk.get("id") or ""),
                "document_id": str(chunk.get("document_id") or ""),
                "content": chunk.get("content") or "",
                "metadata": chunk.get("metadata") or {},
                "score": chunk.get("score"),
            }
            for chunk in retrieved_chunks
        ]

        user_prompt = self._build_user_prompt(message, used_chunks)
        messages = self._build_messages(history, user_prompt)
        answer_chunks: list[str] = []
        start_time = time.perf_counter()

        yield {
            "type": "meta",
            "session_id": chat_session.id,
            "used_chunks": used_chunks,
        }

        async for chunk in self.llm_service.stream_chat(
            messages=messages,
            model=model_settings.model_key,
            temperature=model_settings.temperature,
            max_tokens=model_settings.max_tokens,
        ):
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
            chunks=used_chunks,
            model_name=model_settings.model_key,
        )
        await db.commit()

    async def get_messages(
        self,
        db: AsyncSession,
        current_user: User,
        session_id: str | int,
    ) -> list[dict[str, Any]]:
        user = current_user
        if not user:
            raise AppException(
                message="用户不存在",
                code=404,
                status_code=404
            )
        parsed_session_id = self._parse_session_id(session_id)
        if parsed_session_id is None:
            return []

        result = await db.execute(
            select(ChatMessage)
            .join(ChatSession, ChatSession.id == ChatMessage.session_id)
            .where(
                ChatMessage.session_id == parsed_session_id,
                ChatSession.user_id == user.id,
                ChatSession.status == "active",
            )
            .order_by(ChatMessage.created_at.asc())
        )
        messages = result.scalars().all()
        return [
            {
                "role": message.role,
                "content": message.content,
                "chunks": (message.metadata_ or {}).get("used_chunks", []),
            }
            for message in messages
        ]

    async def delete_session(
        self,
        db: AsyncSession,
        current_user: User,
        session_id: str | int,
    ) -> bool:
        user = current_user
        if not user:
            raise AppException(
                message="用户不存在",
                code=404,
                status_code=404
            )
        parsed_session_id = self._parse_session_id(session_id)
        if parsed_session_id is None:
            return False

        result = await db.execute(
            select(ChatSession).where(ChatSession.id == parsed_session_id,
                                      ChatSession.user_id == user.id)
        )
        chat_session = result.scalar_one_or_none()
        if chat_session is None:
            return False

        await db.execute(delete(ChatMessage).where(ChatMessage.session_id == parsed_session_id))
        await db.execute(delete(ChatSessionKb).where(ChatSessionKb.session_id == parsed_session_id))
        await db.execute(delete(ChatSession).where(ChatSession.id == parsed_session_id))
        await db.commit()

        return True
