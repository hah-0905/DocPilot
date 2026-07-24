from app.core.config import get_settings
from app.core.redis import redis_client
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from app.db.session import get_db
from app.models.users import User
from starlette import status
from sqlalchemy.ext.asyncio import AsyncSession
from app.utils import security
from app.schemas.users import PasswordChangeRequest, UserCreateRequest, UserLogin, UserUpdateRequest
import uuid
from redis.exceptions import RedisError
from app.models.workspaces import Workspace
from app.models.workspace_members import WorkspaceMember

bearer_scheme = HTTPBearer(auto_error=False)


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


async def create_user(user_data: UserCreateRequest, db: AsyncSession):
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
        password_hash=hashed_password
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

    try:
        await redis_client.set(
            f"login:token:{token}",
            str(user.id),
            ex=get_settings().redis_token_ttl_seconds,
        )
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is temporarily unavailable",
        ) from exc

    return token


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    '''
    获取当前用户
    '''
    if not credentials or not credentials.credentials.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication credentials",
        )
    token = credentials.credentials
    redis_key = f"login:token:{token}"

    # 查询 Redis
    try:
        user_id = await redis_client.get(redis_key)
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is temporarily unavailable",
        ) from exc

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效或过期的登录凭证"
        )

    # 滑动续期（重新设置 7 天过期时间）
    try:
        await redis_client.expire(redis_key, get_settings().redis_token_ttl_seconds)
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is temporarily unavailable",
        ) from exc

    try:
        user_id_int = int(user_id)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication credentials",
        ) from None

    user = await db.get(User, user_id_int)

    # 查询用户
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在"
        )

    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is unavailable",
        )

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
        user_data: UserUpdateRequest,
        db: AsyncSession
):

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

    if user_data.email is not None:
        existing_user = await get_user_by_email(user_data.email, db)
        if existing_user and existing_user.id != user.id:
            raise HTTPException(status_code=400, detail="Email is already in use")
    if user_data.username is not None:
        existing_user = await get_user_by_username(user_data.username, db)
        if existing_user and existing_user.id != user.id:
            raise HTTPException(status_code=400, detail="Username is already in use")

    # 更新用户信息
    if user_data.email is not None:
        user.email = user_data.email
    if user_data.username is not None:
        user.username = user_data.username
    if user_data.display_name is not None:
        user.display_name = user_data.display_name
    await db.commit()
    await db.refresh(user)
    return user


async def change_password(
    user: User,
    password_data: PasswordChangeRequest,
    db: AsyncSession,
) -> User:
    if not security.verify_password(password_data.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")

    user.password_hash = security.get_hash_password(password_data.new_password)
    await db.commit()
    await db.refresh(user)
    return user
