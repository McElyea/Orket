"""
Auth Service - Phase 5: Production Readiness

Handles user authentication, password hashing, and JWT issuance.
"""

from __future__ import annotations

import os
import sqlite3
import threading
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from orket.runtime_paths import resolve_auth_token_blocklist_db_path

# Security configuration
SECRET_KEY: str | None = None
_SECRET_KEY_LOCK = threading.Lock()
_TOKEN_BLOCKLIST: TokenBlocklist | None = None
_TOKEN_BLOCKLIST_LOCK = threading.Lock()

ALGORITHM = "HS256"
DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES = 60


def _resolve_access_token_expire_minutes() -> int:
    raw = str(os.getenv("ORKET_AUTH_TOKEN_EXPIRE_MINUTES") or "").strip()
    if not raw:
        return DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES
    return max(1, value)


ACCESS_TOKEN_EXPIRE_MINUTES = _resolve_access_token_expire_minutes()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str | None = None
    jti: str | None = None


class TokenBlocklist:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = resolve_auth_token_blocklist_db_path(db_path)
        self._lock = threading.Lock()
        self._initialized = False

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        with self._lock:
            if self._initialized:
                return
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS revoked_tokens (
                        jti TEXT PRIMARY KEY,
                        revoked_at TEXT NOT NULL,
                        expires_at TEXT
                    )
                    """
                )
                conn.commit()
            self._initialized = True

    def revoke(self, jti: str, *, expires_at: datetime | None = None) -> None:
        token_id = str(jti or "").strip()
        if not token_id:
            raise ValueError("token jti is required for revocation")
        self._ensure_initialized()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO revoked_tokens (jti, revoked_at, expires_at)
                VALUES (?, ?, ?)
                """,
                (
                    token_id,
                    datetime.now(UTC).isoformat(),
                    expires_at.isoformat() if expires_at is not None else None,
                ),
            )
            conn.commit()

    def is_revoked(self, jti: str) -> bool:
        token_id = str(jti or "").strip()
        if not token_id:
            return False
        self._ensure_initialized()
        now_iso = datetime.now(UTC).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM revoked_tokens WHERE expires_at IS NOT NULL AND expires_at < ?",
                (now_iso,),
            )
            row = conn.execute("SELECT 1 FROM revoked_tokens WHERE jti = ? LIMIT 1", (token_id,)).fetchone()
            conn.commit()
        return row is not None


def get_secret_key() -> str:
    global SECRET_KEY
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
    expire = (
        datetime.now(UTC) + expires_delta
        if expires_delta is not None
        else datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "jti": uuid.uuid4().hex})
    encoded_jwt = jwt.encode(to_encode, get_secret_key(), algorithm=ALGORITHM)
    return encoded_jwt


def get_token_blocklist() -> TokenBlocklist:
    global _TOKEN_BLOCKLIST
    with _TOKEN_BLOCKLIST_LOCK:
        if _TOKEN_BLOCKLIST is None:
            _TOKEN_BLOCKLIST = TokenBlocklist()
        return _TOKEN_BLOCKLIST


def verify_access_token(token: str, *, blocklist: TokenBlocklist | None = None) -> TokenData:
    try:
        payload = jwt.decode(token, get_secret_key(), algorithms=[ALGORITHM])
    except JWTError as exc:
        raise ValueError("Invalid access token") from exc
    token_id = str(payload.get("jti") or "").strip()
    resolved_blocklist = blocklist or get_token_blocklist()
    if token_id and resolved_blocklist.is_revoked(token_id):
        raise ValueError("Access token has been revoked")
    subject = str(payload.get("sub") or "").strip() or None
    return TokenData(username=subject, jti=token_id or None)
