from datetime import datetime
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.kb import KnowledgeBase
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.workspaces import Workspace


class KbService:

    async def create_knowledge_base(
            self,
            db: AsyncSession,
            user_id: int,
            workspace_id: int,
            name: str,
            description: str | None = None,
    ) -> KnowledgeBase:
        '''
        创建知识库
        '''
        query = select(Workspace).where(
            Workspace.owner_user_id == user_id,
            Workspace.status == "active",
        )
        
        if workspace_id is not None:
            query = query.where(Workspace.id == workspace_id)
        else:
            query = query.order_by(Workspace.id.asc())
        
        workspace = await db.scalar(query)
        
        if not workspace:
            raise HTTPException(
                status_code=403,
                detail="无权访问该工作空间或默认工作空间不存在"
            )

        normalized_name = name.strip()
        if not normalized_name:
            raise HTTPException(status_code=422, detail="知识库名称不能为空")

        existing_kb = await db.scalar(
            select(KnowledgeBase).where(
                KnowledgeBase.workspace_id == workspace.id,
                KnowledgeBase.name == normalized_name,
            )
        )

        if existing_kb:
            if existing_kb.status == "deleted":
                existing_kb.description = description
                existing_kb.status = "active"
                existing_kb.deleted_at = None
                existing_kb.created_by = user_id
                db.add(existing_kb)
                await db.commit()
                await db.refresh(existing_kb)
                return existing_kb

            raise HTTPException(
                status_code=409,
                detail="当前工作空间中已存在同名知识库"
            )

        kb = KnowledgeBase(
            workspace_id=workspace.id,
            name=normalized_name,
            description=description,
            created_by=user_id,
        )

        db.add(kb)
        try:
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise HTTPException(
                status_code=409,
                detail="当前工作空间中已存在同名知识库"
            ) from exc
        await db.refresh(kb)

        return kb

    async def list_knowledge_bases(
            self,
            db: AsyncSession,
            user_id: int,
    ) -> list[KnowledgeBase]:
        '''
        列出知识库
        '''
        result = await db.execute(
            select(KnowledgeBase).join(Workspace).where(
                Workspace.owner_user_id == user_id,
                Workspace.status == "active",
                KnowledgeBase.status == "active",
            )
        )
        return result.scalars().all()

    async def get_knowledge_base(
            self,
            db: AsyncSession,
            user_id: int,
            kb_id: int,
    ) -> KnowledgeBase:
        '''
        获取知识库
        '''
        kb = await self.select_knowledge_workspace(db, user_id, kb_id)
        if not kb:
            raise HTTPException(
                status_code=404,
                detail="知识库不存在"
            )
        return kb

    async def update_knowledge_base(
            self,
            db: AsyncSession,
            user_id: int,
            kb_id: int,
            update_data: dict,
    ) -> KnowledgeBase:
        '''
        更新知识库
        '''
        kb = await self.select_knowledge_workspace(db, user_id, kb_id)

        if not kb:
            raise HTTPException(
                status_code=404,
                detail="知识库不存在"
            )
        
        for key, value in update_data.items():
            setattr(kb, key, value)

        await db.commit()
        await db.refresh(kb)
        return kb

    async def delete_knowledge_base(
            self,
            db: AsyncSession,
            user_id: int,
            kb_id: int,
    ) -> None:
        '''
        删除知识库
        '''
        kb = await self.select_knowledge_workspace(db, user_id, kb_id)
        if not kb:
            raise HTTPException(
                status_code=404,
                detail="知识库不存在"
            )

        kb.status = "deleted"
        kb.deleted_at = datetime.now()
        db.add(kb)
        await db.commit()

    async def select_knowledge_workspace(
            self,
            db: AsyncSession,
            user_id: int,
            kb_id: int
    ) -> KnowledgeBase:
        '''
        查询知识库和工作空间权限
        '''
        result = await db.execute(
                    select(KnowledgeBase).join(Workspace).where(
                        KnowledgeBase.id == kb_id,
                        Workspace.owner_user_id == user_id,
                        Workspace.status == "active",
                        KnowledgeBase.status == "active",
                    )
                )
        return result.scalar_one_or_none()
