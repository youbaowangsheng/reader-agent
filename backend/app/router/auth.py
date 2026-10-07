from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from uuid import UUID
from app.core.security import (
    create_access_token,
    decode_access_token,
    get_current_user,
    AuthUser,
    validate_login_credentials,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user: dict


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    """Development login with configured credential map."""
    email = req.email.strip().lower()
    if not validate_login_credentials(email, req.password):
        raise HTTPException(401, "Invalid email or password")
    token = create_access_token(email)
    payload = decode_access_token(token)
    return LoginResponse(
        token=token,
        user={"id": payload["sub"], "email": payload["email"]},
    )


@router.get("/me")
async def get_me(user: AuthUser = Depends(get_current_user)):
    """Get current user bound to Bearer token."""
    return {
        "user": {"id": str(user.id), "email": user.email}
    }
