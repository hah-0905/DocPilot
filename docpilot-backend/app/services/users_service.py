from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from app.models.users import AuthActionToken, User
from starlette import status
from sqlalchemy.ext.asyncio import AsyncSession
from app.utils import security
from app.schemas.users import UserInfoBase, UserLogin
import uuid
import hashlib
from app.models.workspaces import Workspace
from app.models.workspace_members import WorkspaceMember


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
        password_hash=hashed_password
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)  # 从数据库读回最新的 user
    return user


async def create_token(email: str, db: AsyncSession):
    '''
    生成 Token + 添加到数据库
    '''
    # 生成 Token + 设置过期时间 → 查询数据库当前用户是否有 Token → 有：更新；没有：添加
    action_type = "email_verify"
    token = str(uuid.uuid4())
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

    # timedelta(days=7, hours=2, minutes=30, seconds=10)
    expires_at = datetime.now() + timedelta(days=7)
    user = await get_user_by_email(email, db)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    query = select(AuthActionToken).where(
        AuthActionToken.user_id == user.id,
        AuthActionToken.action_type == action_type,
    )
    result = await db.execute(query)
    user_token = result.scalar_one_or_none()

    if user_token:
        user_token.token_hash = token_hash
        user_token.expires_at = expires_at
        user_token.used_at = None
    else:
        user_token = AuthActionToken(
            user_id=user.id,
            token_hash=token_hash,
            action_type=action_type,
            target=user.email,
            expires_at=expires_at,
        )
        db.add(user_token)
    await db.commit()
    return token


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
