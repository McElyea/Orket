from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from orket.runtime.module_registry import (
    ensure_capability_enabled,
    ensure_module_enabled,
    resolve_module_profile,
)


@dataclass(frozen=True)
class CompositionConfig:
    project_root: Path | None = None
    workspace_root: Path | None = None
    module_profile: str | None = None


def _resolved_profile(config: CompositionConfig | None) -> str:
    explicit = config.module_profile if config else None
    return resolve_module_profile(explicit_profile=explicit)


def create_engine(config: CompositionConfig | None = None) -> Any:
    profile = _resolved_profile(config)
    ensure_module_enabled("engine", profile)

    from orket.orchestration.engine import OrchestrationEngine

    workspace = (config.workspace_root if config and config.workspace_root else Path("workspace/default")).resolve()
    return OrchestrationEngine(workspace)


def require_composition_capability(capability: str, config: CompositionConfig | None = None) -> None:
    """Authorize a requested transport capability without importing its interface."""
    ensure_capability_enabled(capability, _resolved_profile(config))
