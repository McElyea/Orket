"""
Auth Service - Phase 5: Production Readiness

Handles user authentication, password hashing, and JWT issuance.
"""

from __future__ import annotations

import os
import threading
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import jwt
from passlib.context import CryptContext
from pydantic import BaseModel

# Security configuration
SECRET_KEY: str | None = None
_SECRET_KEY_LOCK = threading.Lock()

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 1 day

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str | None = None


def get_secret_key() -> str:
    global SECRET_KEY
    if SECRET_KEY:
        return SECRET_KEY
    with _SECRET_KEY_LOCK:
        if SECRET_KEY:
            return SECRET_KEY
        secret = str(os.getenv("ORKET_AUTH_SECRET") or "").strip()
        if not secret:
            raise RuntimeError(
                "ORKET_AUTH_SECRET environment variable is not set. Refusing to start in insecure mode."
            )
        SECRET_KEY = secret
        return SECRET_KEY


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(UTC) + expires_delta if expires_delta else datetime.now(UTC) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, get_secret_key(), algorithm=ALGORITHM)
    return encoded_jwt
