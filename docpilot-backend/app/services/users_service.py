import asyncio
import hashlib
import hmac
import json

from app.core.redis import get_redis_client
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from app.db.session import get_db
from app.models.users import User
from starlette import status
from sqlalchemy.ext.asyncio import AsyncSession
from app.utils import security
from app.schemas.users import PasswordChangeRequest, UserInfoBase, UserInfoUpdate, UserLogin
import uuid
from app.models.workspaces import Workspace
from app.models.workspace_members import WorkspaceMember

bearer_scheme = HTTPBearer()
TOKEN_TTL_SECONDS = 60 * 60 * 24 * 7


def _credential_version(password_hash: str) -> str:
    """Bind sessions to credentials without putting the password hash in Redis."""
    return hashlib.sha256(password_hash.encode("utf-8")).hexdigest()


def require_redis_client():
    """Return the token store or fail with a clear service error."""
    client = get_redis_client()
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is temporarily unavailable",
        )
    return client


async def get_user_by_email(email: str, db: AsyncSession):
    '''
    根据邮件获取用户
    :param email: 用户邮件
    :param db: 数据库连接
    :return: 用户对象
    '''
    query = select(User).where(User.email == email)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def get_user_by_username(username: str, db: AsyncSession):
    '''
    根据用户名获取用户
    :param username: 用户名
    :param db: 数据库连接
    :return: 用户对象
    '''
    query = select(User).where(User.username == username)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def create_user(user_data: UserInfoBase, db: AsyncSession):
    '''
    创建用户
    :param user_data: 用户信息
    :param db: 数据库连接
    :return: 用户对象
    '''
    # 密码加密处理 -> add
    hashed_password = security.get_hash_password(user_data.password)
    user = User(
        username=user_data.username,
        email=user_data.email,
        password_hash=hashed_password,
        display_name=user_data.display_name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)  # 从数据库读回最新的 user
    return user


async def create_token(email: str, db: AsyncSession):
    '''
    生成登录 Token，并缓存到 Redis
    '''
    # 生成 Token + 设置过期时间 → 查询数据库当前用户是否有 Token → 有：更新；没有：添加
    # action_type = "login"
    # token = str(uuid.uuid4())
    # token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

    # # timedelta(days=7, hours=2, minutes=30, seconds=10)
    # expires_at = datetime.now() + timedelta(days=7)
    user = await get_user_by_email(email, db)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    # query = select(AuthActionToken).where(
    #     AuthActionToken.user_id == user.id,
    #     AuthActionToken.action_type == action_type,
    # )
    # result = await db.execute(query)
    # user_token = result.scalar_one_or_none()

    token = str(uuid.uuid4())

    redis_client = require_redis_client()
    await redis_client.set(
        f"login:token:{token}",
        json.dumps({
            "user_id": user.id,
            "credential_version": _credential_version(user.password_hash),
        }),
        ex=TOKEN_TTL_SECONDS,
    )

    return token


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    '''
    获取当前用户
    '''
    token = credentials.credentials
    redis_key = f"login:token:{token}"

    # 查询 Redis
    redis_client = require_redis_client()
    token_data = await redis_client.get(redis_key)

    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效或过期的登录凭证"
        )

    try:
        session = json.loads(token_data)
        if not isinstance(session, dict):
            raise ValueError("Legacy or invalid session")
        user_id = session["user_id"]
        version = session["credential_version"]
        if type(user_id) is not int or user_id <= 0 or not isinstance(version, str):
            raise ValueError("Invalid session fields")
    except (ValueError, TypeError, KeyError) as exc:
        # Old ID-only sessions cannot prove which password issued them.
        # Fail closed instead of upgrading a potentially revoked session.
        raise HTTPException(status_code=401, detail="登录凭证已失效，请重新登录") from exc

    user = await db.get(User, user_id)

    # 查询用户
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在"
        )

    if not hmac.compare_digest(
        version.encode("utf-8"),
        _credential_version(user.password_hash).encode("utf-8"),
    ):
        raise HTTPException(status_code=401, detail="密码已变更，请重新登录")

    # Only valid sessions receive sliding expiry.
    await redis_client.expire(redis_key, TOKEN_TTL_SECONDS)

    return user


async def authenticate_user(user_data: UserLogin, db: AsyncSession):
    """
    用户登录验证
    :param user_data: 用户登录数据
    :param db: 数据库连接
    :return: 用户信息
    """
    user = None

    if user_data.email:
        user = await get_user_by_email(user_data.email, db)
    elif user_data.username:
        user = await get_user_by_username(user_data.username, db)
    # 判断用户是否存在
    if not user:
        return None
    if not security.verify_password(user_data.password, user.password_hash):
        return None

    return user


async def create_workspace(user_data, db: AsyncSession):
    """
    创建默认工作空间
    :param user_id: 用户ID
    :param db: 数据库连接
    :return: None
    """
    workspace = Workspace(
        name=f"{user_data.username} 的默认空间",
        description="系统默认创建的个人工作空间",
        owner_user_id=user_data.id,
        status="active",
    )
    db.add(workspace)
    await db.flush()  # 刷新以获取 workspace.id

    # 创建工作空间成员记录，设置为 owner 角色
    workspace_member = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=user_data.id,
        role="owner"
    )
    db.add(workspace_member)

    await db.commit()


async def update_user_info(
        user_id: int,
        user_data: UserInfoUpdate,
        db: AsyncSession,
        *,
        current_user: User,
):
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="无权修改该账号")

    result = await db.execute(
        select(User).where(
            User.id == user_id
        )
    )
    user = result.scalar_one_or_none()

    if not user:  # 找不到用户
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    for field in ("username", "email", "display_name"):
        if field in user_data.model_fields_set:
            setattr(user, field, getattr(user_data, field))

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="用户名或邮箱已被使用") from exc
    await db.refresh(user)
    return user


async def change_password(
    request: PasswordChangeRequest,
    db: AsyncSession,
    *,
    current_user: User,
) -> None:
    old_hash = current_user.password_hash
    if not await asyncio.to_thread(
        security.verify_password, request.current_password, old_hash
    ):
        raise HTTPException(status_code=400, detail="当前密码不正确")
    if await asyncio.to_thread(security.verify_password, request.new_password, old_hash):
        raise HTTPException(status_code=422, detail="新密码不能与当前密码相同")

    new_hash = await asyncio.to_thread(security.get_hash_password, request.new_password)
    # Compare-and-swap prevents a concurrent request verified with an old hash
    # from overwriting a newer password. Committing invalidates every token
    # whose credential_version was derived from the old hash.
    result = await db.execute(
        update(User)
        .where(User.id == current_user.id, User.password_hash == old_hash)
        .values(password_hash=new_hash)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        await db.rollback()
        raise HTTPException(status_code=409, detail="密码已变更，请重新登录后重试")
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise
