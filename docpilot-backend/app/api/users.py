from fastapi import APIRouter, Depends, HTTPException, security
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.users import UserAuthResponse, UserInfoBase, UserInfoResponse, UserLogin
from app.db.session import get_db
from app.services import users_service as users
from app.utils.response import ApiResponse
from starlette import status

router = APIRouter(prefix="/api/user", tags=["用户相关接口"])


@router.post("/register")
async def register(
    request: UserInfoBase,
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
