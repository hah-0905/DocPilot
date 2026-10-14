import asyncio
import json

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.models.user_model_config import UserModelConfig
from app.schemas.personal_model import PersonalModelStatus, PersonalModelUpdate
from app.services.model_catalog import validate_model


UNAVAILABLE = "个人模型凭据功能不可用，请联系管理员配置有效的加密主密钥"


def credential_cipher() -> Fernet:
    master_key = get_settings().personal_model_master_key
    try:
        if not master_key:
            raise ValueError()
        return Fernet(master_key.get_secret_value().encode("ascii"))
    except (ValueError, UnicodeError):
        raise HTTPException(503, UNAVAILABLE) from None


def credentials_available() -> bool:
    try:
        credential_cipher()
        return True
    except HTTPException:
        return False


def encrypt_key(key: str, user_id: int, provider_id: str) -> str:
    # Bind the authenticated payload to its owner and provider, preventing row swaps.
    payload = json.dumps({"user_id": user_id, "provider_id": provider_id, "key": key})
    return credential_cipher().encrypt(payload.encode()).decode()


def decrypt_key(row: UserModelConfig) -> str:
    cipher = credential_cipher()
    try:
        payload = json.loads(cipher.decrypt(row.encrypted_credential.encode()))
        if payload["user_id"] != row.user_id or payload["provider_id"] != row.provider_id:
            raise ValueError()
        return payload["key"]
    except (InvalidToken, ValueError, KeyError, TypeError, UnicodeError):
        raise HTTPException(503, "个人模型凭据无法解密，请重新保存 API Key") from None


class PersonalModelService:
    async def get_row(self, db, user_id: int):
        return (await db.execute(select(UserModelConfig).where(
            UserModelConfig.user_id == user_id,
        ))).scalar_one_or_none()

    def status(self, row) -> PersonalModelStatus:
        available = credentials_available()
        return PersonalModelStatus(
            available=available, configured=row is not None,
            enabled=bool(row and row.enabled),
            provider_id=row.provider_id if row else None,
            model_name=row.model_name if row else None,
            key_mask=f"••••{row.credential_last_four}" if row else None,
            unavailable_reason=None if available else UNAVAILABLE,
        )

    async def read(self, db, user_id: int):
        return self.status(await self.get_row(db, user_id))

    async def candidate_key(self, row, request):
        credential_cipher()
        if request.api_key is not None:
            return request.api_key.get_secret_value()
        if row is None:
            raise HTTPException(422, "首次保存需要提供 API Key")
        if row.provider_id != request.provider_id:
            raise HTTPException(422, "切换服务商时需要提供新的 API Key")
        return decrypt_key(row)

    async def save(self, db, user_id: int, request: PersonalModelUpdate):
        credential_cipher()
        validate_model(request.provider_id, request.model_name)
        row = await self.get_row(db, user_id)
        key = await self.candidate_key(row, request)
        encrypted = (row.encrypted_credential if row is not None and request.api_key is None
                     else encrypt_key(key, user_id, request.provider_id))
        if row is None:
            row = UserModelConfig(user_id=user_id)
            db.add(row)
        row.provider_id = request.provider_id
        row.model_name = request.model_name
        row.encrypted_credential = encrypted
        row.credential_last_four = key[-4:]
        row.enabled = request.enabled
        try:
            await db.commit()
            await db.refresh(row)
        except SQLAlchemyError:
            await db.rollback()
            raise HTTPException(409, "个人模型配置保存失败，请刷新后重试") from None
        return self.status(row)

    async def delete(self, db, user_id: int):
        # Deletion remains possible even when the encryption key is unavailable.
        await db.execute(delete(UserModelConfig).where(UserModelConfig.user_id == user_id))
        await db.commit()
        return self.status(None)

    async def test_connection(self, db, user_id: int, request: PersonalModelUpdate):
        from app.services.llm_service import LLMService
        from app.services.model_runtime import ModelRuntime

        credential_cipher()
        provider = validate_model(request.provider_id, request.model_name)
        key = await self.candidate_key(await self.get_row(db, user_id), request)
        runtime = ModelRuntime(
            model_key=request.model_name, api_key=key, base_url=provider.base_url,
            source="personal", temperature=0, max_tokens=16,
        )
        try:
            async with asyncio.timeout(12):
                await LLMService().chat(
                    [{"role": "user", "content": "Reply OK."}], runtime=runtime, timeout=10,
                )
        except TimeoutError:
            raise HTTPException(504, "个人模型连接测试超时，请稍后重试") from None
        return {"success": True, "message": "连接成功（可能产生少量费用）"}


personal_model_service = PersonalModelService()
