from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select

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

        kb = KnowledgeBase(
            workspace_id=workspace.id,
            name=name,
            description=description,
            created_by=user_id,
        )

        db.add(kb)
        await db.commit()
        await db.refresh(kb)

        return kb

    async def list_knowledge_bases(
            self,
            db: AsyncSession,
            user_id: int,
    ) -> list[KnowledgeBase]:
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
        result = await db.execute(
            select(KnowledgeBase).join(Workspace).where(
                KnowledgeBase.id == kb_id,
                Workspace.owner_user_id == user_id,
                Workspace.status == "active",
                KnowledgeBase.status == "active",
            )
        )
        kb = result.scalar_one_or_none()
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
        # 查询知识库和工作空间权限
        result = await db.execute(
            select(KnowledgeBase).join(Workspace).where(
                KnowledgeBase.id == kb_id,
                Workspace.owner_user_id == user_id,
                Workspace.status == "active",
                KnowledgeBase.status == "active",
            )
        )
        kb = result.scalar_one_or_none()

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
        # 查询知识库和工作空间权限
        result = await db.execute(
            select(KnowledgeBase).join(Workspace).where(
                KnowledgeBase.id == kb_id,
                Workspace.owner_user_id == user_id,
                Workspace.status == "active",
                KnowledgeBase.status == "active",
            )
        )
        kb = result.scalar_one_or_none()
        if not kb:
            raise HTTPException(
                status_code=404,
                detail="知识库不存在"
            )

        kb.status = "deleted"
        kb.deleted_at = datetime.now()
        db.add(kb)
        await db.commit()
