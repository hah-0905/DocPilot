from fastapi import APIRouter


router = APIRouter(prefix="/api/settings", tags=["设置相关接口"])

@router.put("/settings/userInfo")
async def update_user_info():
    """
    更新用户信息
    """
    return {"message": "更新成功"}