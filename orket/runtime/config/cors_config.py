from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class CorsConfig:
    allow_origins: list[str]
    allow_methods: list[str]
    allow_headers: list[str]
    allow_credentials: bool = False


def _split_origins(raw_value: str) -> list[str]:
    return [origin.strip() for origin in raw_value.split(",") if origin.strip()]


def resolve_cors_config(env: Mapping[str, str] | None = None) -> CorsConfig:
    source = os.environ if env is None else env
    origins = _split_origins(str(source.get("ORKET_ALLOWED_ORIGINS", "") or ""))
    return CorsConfig(
        allow_origins=origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Authorization", "X-API-Key"],
    )
