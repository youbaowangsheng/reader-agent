from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.model.database import get_db
from app.model.push_token import PushToken
from app.core.security import get_current_user, AuthUser

router = APIRouter(prefix="/api/push", tags=["push"])


class PushRegisterRequest(BaseModel):
    token: str
    platform: str = "capacitor"


@router.post("/register")
async def register_push_token(
    req: PushRegisterRequest,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """App 内注册 device token，用于每日推送。幂等：同 token 已存在则更新归属。"""
    if not req.token:
        return {"status": "ok"}
    existing = (await db.execute(select(PushToken).where(PushToken.token == req.token))).scalar_one_or_none()
    if existing:
        if existing.user_id != user.id:
            existing.user_id = user.id
        if existing.platform != req.platform:
            existing.platform = req.platform
        return {"status": "ok"}
    db.add(PushToken(user_id=user.id, token=req.token, platform=req.platform))
    return {"status": "ok"}
