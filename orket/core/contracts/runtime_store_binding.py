"""Immutable storage provenance; it grants no workload or effect authorization."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from orket.core.domain.outward_authorization import args_hash


class LegacyRuntimeSessionBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    session_id: str = Field(min_length=1)
    original_runtime_db: str = Field(min_length=1)
    request_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


class RuntimeStoreMigrationBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["runtime_store_binding.v1"] = "runtime_store_binding.v1"
    runtime_db: str
    control_plane_db: str
    source_control_plane_db: str
    legacy_invocation_root: str
    source_snapshot_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    actor_ref: str = Field(min_length=1)
    sessions: tuple[LegacyRuntimeSessionBinding, ...]

    @model_validator(mode="after")
    def validate_paths_and_sessions(self):
        if not all(
            Path(value).is_absolute()
            for value in (
                self.runtime_db,
                self.control_plane_db,
                self.source_control_plane_db,
                self.legacy_invocation_root,
            )
        ):
            raise ValueError("E_RUNTIME_STORE_BINDING_ABSOLUTE_PATH_REQUIRED")
        if len({item.session_id for item in self.sessions}) != len(self.sessions):
            raise ValueError("E_RUNTIME_STORE_BINDING_DUPLICATE_SESSION")
        if any(Path(item.original_runtime_db).is_absolute() for item in self.sessions):
            raise ValueError("E_RUNTIME_STORE_BINDING_RELATIVE_HISTORY_REQUIRED")
        return self

    def digest(self) -> str:
        return args_hash(self.model_dump(mode="json"))
