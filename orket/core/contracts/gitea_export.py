"""Content-addressed export intent retained before a remote mutation."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class GiteaExportIntent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["gitea_export_intent.v1"] = "gitea_export_intent.v1"
    binding: dict[str, Any]
    run_id: str
    commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    base_commit: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")
    run_path: str
