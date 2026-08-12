from fastapi import HTTPException
from fastapi import status
from app.models.users import User
from sqlalchemy import select
from app.schemas.users import UserInfoUpdate
from app.schemas.settings import ModelSettingsUpdate, ReportSettingsUpdate, RetrievalSettingsUpdate
from app.models.workspace_members import WorkspaceMember
from app.models.workspace_model_settings import WorkspaceModelSettings
from app.models.workspace_retrieval_settings import WorkspaceRetrievalSettings
from app.models.workspace_model_settings import WorkspaceModelSettings
from app.models.workspace_report_settings import WorkspaceReportSettings

SUPPORTED_MODELS = {
    "deepseek-chat",
    "deepseek-reasoner",
}


class SettingsService:

    async def update_user_info(
            self,
            db,
            user_id: int,
            user_data: UserInfoUpdate
    ):
        '''
        更新用户信息
        '''
        # 查询用户是否存在-> 存在：更新；不存在：报错“用户不存在”
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )

        # 更新用户信息
        if user_data.email is not None:
            user.email = user_data.email
        if user_data.username is not None:
            user.username = user_data.username

        await db.commit()
        await db.refresh(user)
        return user

    async def select_workspace_member(
            self,
            db,
            user_id: int,
            workspace_id: int
    ):
        '''
        查询工作空间成员
        '''
        member = await db.scalar(
            select(WorkspaceMember)
            .where(
                WorkspaceMember.user_id == user_id,
                WorkspaceMember.workspace_id == workspace_id
            )
        )

        if not member:
            raise HTTPException(
                status_code=403,
                detail="无权限更新该工作空间的模型设置"
            )
        if member.role not in ['owner', 'admin']:
            raise HTTPException(
                status_code=403,
                detail="无权限更新该工作空间的模型设置"
            )

        return member

    async def update_model_settings(
            self,
            db,
            user_id: int,
            workspace_id: int,
            request: ModelSettingsUpdate
    ) -> WorkspaceModelSettings:
        '''
        更新模型设置
        '''
        # 查询用户是否有权限更新该工作空间的模型设置
        member = await self.select_workspace_member(
            db,
            user_id,
            workspace_id,
        )

        # 查询工作空间模型是否支持该模型
        update_data = request.model_dump(exclude_unset=True)

        model_name = update_data.get("model_key")
        if model_name and model_name not in SUPPORTED_MODELS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"不支持的模型：{model_name}"
            )

        # 查询该工作空间是否已有设置
        result = await db.execute(
            select(WorkspaceModelSettings).where(
                WorkspaceModelSettings.workspace_id == workspace_id
            )
        )
        model_settings = result.scalar_one_or_none()

        # 没有则创建，有则更新
        if model_settings is None:
            model_settings = WorkspaceModelSettings(
                workspace_id=workspace_id,
                **update_data,
            )
            db.add(model_settings)
        else:
            for field, value in update_data.items():
                setattr(model_settings, field, value)
        await db.commit()
        await db.refresh(model_settings)
        return model_settings

    async def update_retrieval_settings(
            self,
            db,
            user_id: int,
            workspace_id: int,
            request: RetrievalSettingsUpdate
    ) -> WorkspaceRetrievalSettings:
        '''
        更新检索设置
        '''
        # 查询用户是否有权限更新该工作空间的模型设置
        member = await self.select_workspace_member(
            db,
            user_id,
            workspace_id,
        )

        # 只提取用户实际传入的字段
        update_data = request.model_dump(exclude_unset=True)

        # 查询现有设置
        result = await db.execute(
            select(WorkspaceRetrievalSettings).where(
                WorkspaceRetrievalSettings.workspace_id == workspace_id
            )
        )
        retrieval_settings = result.scalar_one_or_none()

        # 不存在则创建
        if retrieval_settings is None:
            retrieval_settings = WorkspaceRetrievalSettings(
                workspace_id=workspace_id,
                **update_data,
            )
            db.add(retrieval_settings)

        # 存在则更新
        else:
            for field, value in update_data.items():
                setattr(retrieval_settings, field, value)

        # 提交事务并刷新对象
        try:
            await db.commit()
            await db.refresh(retrieval_settings)
        except Exception as e:
            await db.rollback()
            raise
        return retrieval_settings

    async def update_report_settings(
            self,
            db,
            user_id: int,
            workspace_id: int,
            request: ReportSettingsUpdate
    ) -> WorkspaceReportSettings:
        '''
        更新报告设置
        '''
        # 查询用户是否有权限更新该工作空间的模型设置
        member = await self.select_workspace_member(
            db,
            user_id,
            workspace_id,
        )

        # 只提取用户实际传入的字段
        update_data = request.model_dump(exclude_unset=True)

        # 查询现有设置
        result = await db.execute(
            select(WorkspaceReportSettings).where(
                WorkspaceReportSettings.workspace_id == workspace_id
            )
        )
        report_settings = result.scalar_one_or_none()

        # 不存在则创建
        if report_settings is None:
            report_settings = WorkspaceReportSettings(
                workspace_id=workspace_id,
                **update_data,
            )
            db.add(report_settings)

        # 存在则更新
        else:
            for field, value in update_data.items():
                setattr(report_settings, field, value)

        # 提交事务并刷新对象
        try:
            await db.commit()
            await db.refresh(report_settings)
        except Exception as e:
            await db.rollback()
            raise
        return report_settings

