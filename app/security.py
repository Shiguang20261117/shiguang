"""密码哈希与 JWT 工具。

- 密码哈希：passlib 的 pbkdf2_sha256 方案（无需额外编译依赖）
- JWT：python-jose 签发 / 校验，算法由 config.JWT_ALGORITHM 指定
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import jwt
from passlib.context import CryptContext

from .config import settings

_pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return _pwd_context.verify(password, hashed_password)
    except (ValueError, TypeError):
        # 哈希格式损坏 / 算法未知时按校验失败处理
        return False


def create_access_token(
    subject: str | int, expires_delta: timedelta | None = None
) -> str:
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """解码 JWT，失败时抛出 jose.exceptions.JWTError 的子类。"""
    return jwt.decode(
        token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
    )
