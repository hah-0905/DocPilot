from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.users import (
    PasswordChangeRequest,
    UserAuthResponse,
    UserCreateRequest,
    UserInfoResponse,
    UserLogin,
    UserUpdateRequest,
)
from app.db.session import get_db
from app.services import users_service as users
from app.utils.response import ApiResponse
from starlette import status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.core.redis import redis_client
from app.services.users_service import bearer_scheme, get_current_user
from app.models.users import User
from redis.exceptions import RedisError

router = APIRouter(prefix="/api/user", tags=["用户相关接口"])


@router.post("/register")
async def register(
    request: UserCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    # 检查用户是否存在
    existing_user = await users.get_user_by_email(request.email, db)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户已存在"
        )
    # 检查用户名是否存在
    existing_username = await users.get_user_by_username(request.username, db)
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在"
        )
    # 创建新用户
    user = await users.create_user(request, db)
    # 创建用户令牌
    token = await users.create_token(email=user.email, db=db)
    # 创建工作空间
    await users.create_workspace(user, db)
    # 构建响应数据
    response_data = UserAuthResponse(
        token=token,
        user_info=UserInfoResponse.model_validate(user)
    )
    return ApiResponse(
        message="注册成功",
        data=response_data
    )


@router.post("/login")
async def login(
    request: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    # 登录逻辑：验证用户是否存在 -> 验证密码 -> 生成 Token  → 响应结果
    user = await users.authenticate_user(request, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )

    token = await users.create_token(email=user.email, db=db)

    return ApiResponse(
        message="登录成功",
        data=UserAuthResponse(
            token=token,
            user_info=UserInfoResponse.model_validate(user)  # 将用户信息转换为响应数据
        )
    )

@router.post("/logout")
async def logout(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
):
    if not credentials or not credentials.credentials.strip():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效或过期的登录凭证")
    token = credentials.credentials
    try:
        await redis_client.delete(f"login:token:{token}")
    except RedisError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="认证服务暂时不可用") from exc
    return ApiResponse(message="退出成功")

@router.patch("/me")
async def update_current_user_info(
    request: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user = await users.update_user_info(current_user.id, request, db)
    return ApiResponse(message="更新成功", data=UserInfoResponse.model_validate(user))


@router.post("/me/password")
async def change_current_user_password(
    request: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await users.change_password(current_user, request, db)
    return ApiResponse(message="密码修改成功")


@router.post("/update/{user_id}", deprecated=True)
async def update_user_info_legacy(
    user_id: int,
    request: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权修改其他用户")
    user = await users.update_user_info(current_user.id, request, db)
    return ApiResponse(message="更新成功", data=UserInfoResponse.model_validate(user))
