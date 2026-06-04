from typing import List

from sqlalchemy import select

from app.utils.response import ApiResponse
from app.services.kb_service import KbService
from app.services.users_service import get_current_user
from app.db.session import get_db
from fastapi import APIRouter, Depends, File, UploadFile
from app.models.users import User
from app.schemas.kb import CreateKnowledgeBaseRequest, KnowledgeBaseResponse, UpdateKnowledgeBaseRequest
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.workspaces import Workspace
from app.services.document_service import DocumentService

router = APIRouter(prefix="/api/kb", tags=["知识库相关接口"])

kb_service = KbService()
document_service = DocumentService()


@router.post("/knowledge-bases")
async def create_knowledge_base(
    request: CreateKnowledgeBaseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    创建知识库
    """
    kb = await kb_service.create_knowledge_base(
        db,
        user_id=current_user.id,
        workspace_id=request.workspace_id,
        name=request.name,
        description=request.description
    )
    return ApiResponse(
        message="创建成功",
        data=KnowledgeBaseResponse.model_validate(kb)
    )


@router.get("/knowledge-bases")
async def list_knowledge_bases(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    列出知识库
    """
    kb_list = await kb_service.list_knowledge_bases(
        db,
        user_id=current_user.id
    )
    return ApiResponse(
        message="查询成功",
        data=[KnowledgeBaseResponse.model_validate(kb) for kb in kb_list]
    )


@router.get("/knowledge-bases/{kb_id}")
async def knowledge_base_detail(
    kb_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取知识库
    """
    kb = await kb_service.get_knowledge_base(
        db,
        user_id=current_user.id,
        kb_id=kb_id
    )
    return ApiResponse(
        message="查询成功",
        data=KnowledgeBaseResponse.model_validate(kb)
    )


@router.put("/knowledge-bases/{kb_id}")
async def update_knowledge_base(
    kb_id: int,
    request: UpdateKnowledgeBaseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    更新知识库
    """
    kb = await kb_service.update_knowledge_base(
        db,
        user_id=current_user.id,
        kb_id=kb_id,
        update_data=request.model_dump(exclude_unset=True)
    )
    return ApiResponse(
        message="更新成功",
        data=KnowledgeBaseResponse.model_validate(kb)
    )


@router.delete("/knowledge-bases/{kb_id}")
async def delete_knowledge_base(
    kb_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    删除知识库
    """
    await kb_service.delete_knowledge_base(
        db,
        user_id=current_user.id,
        kb_id=kb_id
    )
    return ApiResponse(
        message="删除成功"
    )


@router.post("/knowledge-bases/{kb_id}/documents/upload")
async def upload_documents(
    kb_id: int,
    current_user: User = Depends(get_current_user),
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db)
):
    """
    上传文档
    """
    result = await document_service.upload_documents(
        db,
        user_id=current_user.id,
        kb_id=kb_id,
        files=files
    )
    return ApiResponse(data=result)


@router.get("/knowledge-bases/{kb_id}/documents")
async def list_documents(
    kb_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    列出文档
    """
    files = await document_service.list_documents(
        db,
        user_id=current_user.id,
        kb_id=kb_id
    )
    data = [
        {
            "id": file.id,
            "name": file.title,
            "type": file.file_ext,
            "status": file.parse_status,
            "updated_at": file.updated_at,
            "chunks": await document_service.count_chunks(
                db,
                file.id,
                kb_id=kb_id
            )
        }
        for file in files
    ]

    return ApiResponse(data=data)

@router.delete("/knowledge-bases/{kb_id}/documents/{document_id}")
async def delete_document(
    document_id: int,
    kb_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    删除文档
    """
    deteled = await document_service.delete_document(
        db,
        user_id=current_user.id,
        kb_id=kb_id,
        document_id=document_id
    )
    if not deteled:
        return ApiResponse(
            message="删除失败",
            deleted = False
        )
    return ApiResponse(
        document_id = document_id,
        deleted = True
        )
