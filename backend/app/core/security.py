import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from uuid import UUID

from pydantic import BaseModel
from starlette.exceptions import HTTPException
from starlette.requests import Request

from config import get_settings


settings = get_settings()


class AuthUser(BaseModel):
    id: UUID
    email: str


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded.encode("utf-8"))


def _sign(payload_b64: str) -> str:
    digest = hmac.new(
        key=settings.auth_secret_key.encode("utf-8"),
        msg=payload_b64.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    return _b64url_encode(digest)


def _stable_user_id_from_email(email: str) -> UUID:
    import uuid

    return uuid.uuid5(uuid.NAMESPACE_DNS, email.strip().lower())


def create_access_token(email: str) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(hours=settings.auth_token_ttl_hours)
    user_id = _stable_user_id_from_email(email)
    payload = {
        "sub": str(user_id),
        "email": email.strip().lower(),
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    sig = _sign(payload_b64)
    return f"{payload_b64}.{sig}"


def decode_access_token(token: str) -> Dict[str, Any]:
    try:
        payload_b64, sig = token.split(".", 1)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid token format") from exc

    expected = _sign(payload_b64)
    if not hmac.compare_digest(sig, expected):
        raise HTTPException(status_code=401, detail="Invalid token signature")

    try:
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid token payload") from exc

    exp = int(payload.get("exp", 0))
    now_ts = int(datetime.now(timezone.utc).timestamp())
    if exp <= now_ts:
        raise HTTPException(status_code=401, detail="Token expired")

    return payload


def _extract_bearer_token(authorization: str) -> str:
    parts = (authorization or "").strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    return parts[1].strip()


async def get_current_user(request: Request) -> AuthUser:
    token = _extract_bearer_token(request.headers.get("Authorization", ""))
    payload = decode_access_token(token)
    try:
        user_id = UUID(str(payload.get("sub", "")))
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid token subject") from exc
    email = str(payload.get("email", "")).strip().lower()
    if not email:
        raise HTTPException(status_code=401, detail="Invalid token email")
    return AuthUser(id=user_id, email=email)


def verify_user_access(paper_user_id: UUID, requesting_user_id: UUID) -> bool:
    return paper_user_id == requesting_user_id


def validate_login_credentials(email: str, password: str) -> bool:
    """Validate development login credentials from config map."""
    raw = settings.dev_login_users or "{}"
    try:
        users = json.loads(raw)
    except json.JSONDecodeError:
        return False
    if not isinstance(users, dict):
        return False
    expected = users.get(email.strip().lower())
    if not isinstance(expected, str):
        return False
    return secrets.compare_digest(expected, password or "")
