from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import random
import re
import time

from app.core.security import (
    create_access_token_phone,
    decode_access_token,
    get_current_user,
    AuthUser,
)
from app.service.sms import send_sms

router = APIRouter(prefix="/api/auth", tags=["auth"])

# 验证码内存存储（单机够用）：{phone: {"code", "expires_at", "last_sent_at"}}
_codes = {}

CODE_TTL_SEC = 300          # 验证码 5 分钟有效
RESEND_INTERVAL_SEC = 60    # 60 秒内不重复发送
PHONE_RE = re.compile(r"^1[3-9]\d{9}$")


class SendCodeRequest(BaseModel):
    phone: str


class LoginRequest(BaseModel):
    phone: str
    code: str


class LoginResponse(BaseModel):
    token: str
    user: dict


@router.post("/send-code")
async def send_code(req: SendCodeRequest):
    """发送手机号验证码（阿里云短信）。"""
    phone = req.phone.strip()
    if not PHONE_RE.match(phone):
        raise HTTPException(400, "手机号格式不正确")

    now = time.time()
    rec = _codes.get(phone)
    if rec and now - rec.get("last_sent_at", 0) < RESEND_INTERVAL_SEC:
        raise HTTPException(429, "发送太频繁，请稍后再试")

    code = f"{random.randint(0, 999999):06d}"
    _codes[phone] = {"code": code, "expires_at": now + CODE_TTL_SEC, "last_sent_at": now}

    try:
        resp = send_sms(phone, {"code": code})
    except Exception as exc:
        raise HTTPException(502, f"短信发送失败: {exc}") from exc
    if resp.get("Code") != "OK":
        raise HTTPException(502, f"短信发送失败: {resp.get('Message')}")

    return {"ok": True}


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    """手机号 + 验证码登录。"""
    phone = req.phone.strip()
    code = req.code.strip()
    if not PHONE_RE.match(phone):
        raise HTTPException(401, "手机号格式不正确")

    rec = _codes.get(phone)
    if not rec:
        raise HTTPException(401, "请先获取验证码")
    if time.time() > rec.get("expires_at", 0):
        raise HTTPException(401, "验证码已过期，请重新获取")
    if rec.get("code") != code:
        raise HTTPException(401, "验证码错误")

    _codes.pop(phone, None)  # 一次性使用

    token = create_access_token_phone(phone)
    payload = decode_access_token(token)
    return LoginResponse(
        token=token,
        user={"id": payload["sub"], "phone": phone, "email": phone},
    )


@router.get("/me")
async def get_me(user: AuthUser = Depends(get_current_user)):
    """Get current user bound to Bearer token."""
    return {
        "user": {"id": str(user.id), "email": user.email}
    }
