from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.users import UserInfoUpdate
from app.services.users_service import get_current_user
from app.models.users import User
from app.services.settings_service import SettingsService
from app.schemas.settings import ModelSettingsUpdate, RetrievalSettingsUpdate
from app.schemas.settings import ReportSettingsUpdate


router = APIRouter(prefix="/api/settings", tags=["设置相关接口"])

settingsService = SettingsService()


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
    print("current_user.id =", current_user.id)
    print("current_user.id type =", type(current_user.id))
    print("user_id =", user_id)
    print("user_id type =", type(user_id))

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