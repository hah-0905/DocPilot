from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.personal_model import PersonalModelStatus, PersonalModelUpdate
from app.services.model_catalog import platform_models, providers
from app.services.personal_model_service import personal_model_service
from app.services.users_service import get_current_user


class CredentialRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def guarded_handler(request: Request):
            chunks = []
            size = 0
            async for chunk in request.stream():
                size += len(chunk)
                if size > 8192:
                    raise HTTPException(413, "个人模型配置请求过大")
                chunks.append(chunk)
            request._body = b"".join(chunks)
            try:
                response = await handler(request)
            except RequestValidationError:
                raise HTTPException(422, "个人模型配置参数无效，请检查服务商、模型和 API Key 格式") from None
            response.headers["Cache-Control"] = "no-store"
            return response

        return guarded_handler


router = APIRouter(prefix="/api/settings", tags=["个人模型配置"], route_class=CredentialRoute)


@router.get("/model-catalog")
async def model_catalog(current_user=Depends(get_current_user)):
    return {
        "platform_default_model": get_settings().model_name,
        "platform_models": platform_models(),
        "providers": [
            {"id": p.id, "label": p.label, "models": p.models}
            for p in providers().values()
        ],
    }


@router.get("/personal-model", response_model=PersonalModelStatus)
async def read_personal_model(
    current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    return await personal_model_service.read(db, current_user.id)


@router.put("/personal-model", response_model=PersonalModelStatus)
async def save_personal_model(
    request: PersonalModelUpdate,
    current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    return await personal_model_service.save(db, current_user.id, request)


@router.post("/personal-model/test")
async def test_personal_model(
    request: PersonalModelUpdate,
    current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    return await personal_model_service.test_connection(db, current_user.id, request)


@router.delete("/personal-model", response_model=PersonalModelStatus)
async def delete_personal_model(
    current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    return await personal_model_service.delete(db, current_user.id)
