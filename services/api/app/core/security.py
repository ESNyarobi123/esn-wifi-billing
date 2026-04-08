from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, jwt

from app.core.config import settings


def _bcrypt_secret(password: str) -> bytes:
    """bcrypt truncates at 72 bytes; match common auth limits explicitly."""
    pw = password.encode("utf-8")
    if len(pw) > 72:
        pw = pw[:72]
    return pw


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_bcrypt_secret(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_bcrypt_secret(password), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _fernet() -> Fernet | None:
    key = (settings.router_credentials_fernet_key or "").strip()
    if not key:
        return None
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_secret(plain: str) -> str:
    f = _fernet()
    if f is None:
        raise RuntimeError("ROUTER_CREDENTIALS_FERNET_KEY is not set; cannot encrypt router secrets")
    return f.encrypt(plain.encode()).decode()


def decrypt_secret(token: str) -> str:
    f = _fernet()
    if f is None:
        raise RuntimeError("ROUTER_CREDENTIALS_FERNET_KEY is not set; cannot decrypt router secrets")
    try:
        return f.decrypt(token.encode()).decode()
    except InvalidToken as e:
        raise ValueError("invalid encrypted credential") from e


def create_access_token(subject: str, extra: dict[str, Any] | None = None) -> str:
    now = datetime.now(UTC)
    exp = now + timedelta(minutes=settings.jwt_access_expire_minutes)
    claims: dict[str, Any] = {
        "sub": subject,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    if extra:
        claims.update(extra)
    return jwt.encode(claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str) -> str:
    now = datetime.now(UTC)
    exp = now + timedelta(days=settings.jwt_refresh_expire_days)
    claims = {
        "sub": subject,
        "type": "refresh",
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": secrets.token_urlsafe(16),
    }
    return jwt.encode(claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])


def decode_token_optional_type(token: str, expected_type: str) -> dict[str, Any]:
    try:
        payload = decode_token(token)
    except JWTError as e:
        raise ValueError("invalid token") from e
    if payload.get("type") != expected_type:
        raise ValueError("wrong token type")
    return payload
