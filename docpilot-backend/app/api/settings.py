import logging
import io
import uuid
import asyncio
from PIL import Image,ImageOps, UnidentifiedImageError
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.users import UserInfoUpdate
from app.services.users_service import get_current_user
from app.models.users import User
from app.services.settings_service import SettingsService
from app.schemas.settings import ModelSettingsUpdate, RetrievalSettingsUpdate
from app.schemas.settings import ReportSettingsUpdate
from app.services.oss_service import oss_service


router = APIRouter(prefix="/api/settings", tags=["设置相关接口"])

settingsService = SettingsService()

logger = logging.getLogger(__name__)

# 头像大小限制
MAX_AVATAR_SIZE = 2 * 1024 * 1024
AVATAR_SIZE = (512, 512)

# 允许的图片类型
ALLOWED_AVATAR_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}


@router.put("/userInfo/{user_id}")
async def update_user_info(
    user_id: int,
    user_data: UserInfoUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    更新用户信息
    """
    if current_user.id != user_id:
        raise HTTPException(
            status_code=403,
            detail="无权限更新其他用户信息"
        )

    user = await settingsService.update_user_info(
        db,
        user_id,
        user_data
    )

    return user


@router.put("/avatar")
async def update_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    更新用户头像
    """
    # 检查文件类型
    if file.content_type not in ALLOWED_AVATAR_TYPES:
        raise HTTPException(
            status_code=422,
            detail="不支持的文件类型"
        )

    file_data = await file.read()

    if not file_data:
        raise HTTPException(
            status_code=422,
            detail="文件内容不能为空"
        )

    if len(file_data) > MAX_AVATAR_SIZE:
        raise HTTPException(
            status_code=422,
            detail="文件大小超出限制"
        )

    # 实际解析图片，防止伪造 Content-Type
    try:
        image = Image.open(io.BytesIO(file_data))
        image.load()  # 确保图片可以被完全加载

        image = ImageOps.exif_transpose(image)
        image = ImageOps.fit(
            image.convert("RGB"),
            AVATAR_SIZE,
            method=Image.Resampling.LANCZOS
        )
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
    ):
        raise HTTPException(
            status_code=422,
            detail="图片文件无效或无法解析",
        )

    # 统一转为 WebP
    output = io.BytesIO()
    image.save(
        output,
        format="WEBP",
        quality=85,
        method=6,
    )
    avatar_data = output.getvalue()

    new_avatar_key = (
        f"avatars/{current_user.id}/"
        f"{uuid.uuid4().hex}.webp"
    )

    old_avatar_key = current_user.avatar_url

    # 上传新头像
    try:
        await asyncio.to_thread(
            oss_service.upload_avatar,
            new_avatar_key,
            avatar_data,
        )
    except Exception:
        logger.exception("Failed to upload avatar to OSS")

        raise HTTPException(
            status_code=500,
            detail="头像上传到 OSS 失败",
        )

    # 更新数据库
    try:
        current_user.avatar_url = new_avatar_key

        await db.commit()
        await db.refresh(current_user)
    except Exception:
        await db.rollback()

        # 数据库更新失败，删除刚上传的新头像
        try:
            await asyncio.to_thread(
                oss_service.delete_avatar,
                new_avatar_key,
            )
        except Exception:
            logger.exception(
                "Failed to clean new avatar after database error"
            )

        raise HTTPException(
            status_code=500,
            detail="头像信息保存失败",
        )

    # 数据库成功后删除旧头像
    if (
        old_avatar_key
        and old_avatar_key != new_avatar_key
        and old_avatar_key.startswith("avatars/")
    ):
        try:
            await asyncio.to_thread(
                oss_service.delete_avatar,
                old_avatar_key,
            )
        except Exception:
            # 删除旧头像失败不影响本次更新
            logger.exception("Failed to delete old avatar")

    signed_url = await asyncio.to_thread(
        oss_service.get_signed_url,
        new_avatar_key,
        3600,
    )

    return {
        "avatar_key": new_avatar_key,
        "avatar_url": signed_url,
        "expires_in": 3600,
    }

@router.put("/model/{workspace_id}")
async def update_model_settings(
    workspace_id: int,
    request: ModelSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    '''
    更新工作空间模型设置
    '''
    return await settingsService.update_model_settings(
        db=db,
        user_id=current_user.id,
        workspace_id=workspace_id,
        request=request
    )


@router.put("/retrieval/{workspace_id}")
async def update_retrieval_settings(
    workspace_id: int,
    request: RetrievalSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    '''
    更新工作空间检索设置
    '''
    return await settingsService.update_retrieval_settings(
        db=db,
        user_id=current_user.id,
        workspace_id=workspace_id,
        request=request
    )


@router.put("/report/{workspace_id}")
async def update_report_settings(
    workspace_id: int,
    request: ReportSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    '''
    更新工作空间报告设置
    '''
    return await settingsService.update_report_settings(
        db=db,
        user_id=current_user.id,
        workspace_id=workspace_id,
        request=request
    )
