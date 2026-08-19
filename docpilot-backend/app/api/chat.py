import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from app.services.chat_service import ChatService
from app.schemas.chat import ChatCompletionRequest
from app.db.session import get_db
from app.utils.response import ApiResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.chat import ChatSession
from app.services.users_service import get_current_user
from app.core.exceptions import AppException
from app.services.workspace_settings_service import (
    workspace_settings_service,
)




router = APIRouter(prefix="/api/chat", tags=["chat"])

chat_service = ChatService()


@router.post("/completions")
async def create_chat_completions(
    request: ChatCompletionRequest,
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    '''
    处理聊天补全请求，支持流式和非流式两种响应模式。

    该函数根据请求中的 stream 字段决定返回完整回答还是通过 Server-Sent Events (SSE) 流式返回回答片段。

    参数:
        request (ChatCompletionRequest): 包含会话 ID、用户消息及是否启用流式传输的请求体。
        db (AsyncSession): 由依赖注入提供的异步数据库会话对象，用于访问数据库。

    返回:
        若 request.stream 为 False，返回包含 session_id 和完整 answer 的标准 API 响应；
        若 request.stream 为 True，返回一个 text/event-stream 类型的 StreamingResponse，
        通过事件流逐块发送回答内容，最后以 [DONE] 标记结束。
    '''
    if not request.stream:
        result = await chat_service.chat(
            db=db,
            current_user=current_user,
            session_id=request.session_id,
            message=request.message,
            kb_id=request.kb_id,
        )

        return ApiResponse(
            data={
                "answer": result["answer"],
                "session_id": result.get("session_id"),
                "used_chunks": result.get("used_chunks", []),
            }
        )

    async def event_generator():
        try:
            async for chunk in chat_service.stream_chat(
                db=db,
                current_user=current_user,
                session_id=request.session_id,
                message=request.message,
                kb_id=request.kb_id,
            ):
                # chunk 可以改成 dict {"text": "...", "used_chunks": [...]}
                if isinstance(chunk, dict):
                    yield f"data: {json.dumps(chunk)}\n\n"
                else:
                    # 兼容原来的字符串
                    yield f"data: {json.dumps({'text': chunk, 'used_chunks': []})}\n\n"

            yield "data: [DONE]\n\n"

        except Exception as e:
            yield f"event: error\ndata: {str(e)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )


@router.get("/sessions")
async def list_chat_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user),
) -> ApiResponse:
    """
    获取所有聊天会话列表，并按创建时间升序排序。

    该接口用于查询数据库中所有的聊天会话记录，返回包含会话ID、标题、创建时间和状态的简化信息。

    参数:
        db (AsyncSession): 通过依赖注入提供的异步数据库会话对象，用于执行数据库查询操作。

    返回:
        ApiResponse: 包含会话列表的标准化API响应对象。响应数据结构为：
            {
                "sessions": [
                    {
                        "session_id": int,       # 会话唯一标识
                        "title": str,            # 会话标题
                        "created_at": str,       # ISO 8601格式的创建时间字符串
                        "status": str            # 会话当前状态
                    },
                    ...
                ]
            }
    """
    result = await db.execute(
        select(ChatSession)
        .where(
            ChatSession.user_id == current_user.id,
            ChatSession.status == "active",
        )
        .order_by(ChatSession.created_at.desc())
    )
    sessions = result.scalars().all()

    return ApiResponse(
        data={
            "sessions": [
                {
                    "session_id": session.id,
                    "title": session.title,
                    "created_at": session.created_at.isoformat(),
                    "status": session.status
                }
                for session in sessions
            ]
        }
    )


@router.get("/sessions/{session_id}/messages")
async def get_chat_messages(
    session_id: int,
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> ApiResponse:
    """
    获取指定会话中的所有聊天消息。

    该接口通过会话ID查询对应的聊天记录，并返回包含会话ID和消息列表的响应。

    参数:
        session_id (int): 要查询的聊天会话的唯一标识符。
        db (AsyncSession): 数据库异步会话实例，由依赖注入提供，用于执行数据库操作。

    返回:
        ApiResponse: 包含以下字段的API响应对象：
            - session_id (int): 请求的会话ID；
            - messages (List): 该会话下的所有消息列表。
    """
    messages = await chat_service.get_messages(db, current_user, session_id)
    return ApiResponse(
        data={
            "session_id": session_id,
            "messages": messages,
        }
    )


@router.delete("/sessions/{session_id}")
async def delete_chat_session(
    session_id: int,
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    '''
    删除指定的聊天会话。
    '''
    deleted = await chat_service.delete_session(db, current_user, session_id)

    if not deleted:
        return AppException(
            message="删除失败",
            code=404,
            status_code=404
        )

    return ApiResponse(
        data={
            "session_id": session_id,
            "deleted": True
        }
    )
