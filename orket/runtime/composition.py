from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

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


def create_api_app(config: CompositionConfig | None = None) -> Any:
    profile = _resolved_profile(config)
    ensure_capability_enabled("api.http.v1", profile)

    from orket.interfaces import api as api_module

    project_root = config.project_root if config else None
    return api_module.create_api_app(project_root=project_root)


def create_cli_runtime(config: CompositionConfig | None = None) -> Callable[..., Any]:
    profile = _resolved_profile(config)
    ensure_capability_enabled("cli.runtime", profile)
    from orket.interfaces.cli import run_cli

    return run_cli


def create_webhook_app(config: CompositionConfig | None = None) -> Any:
    profile = _resolved_profile(config)
    ensure_capability_enabled("webhook.gitea.v1", profile)
    from orket import webhook_server as webhook_module

    return webhook_module.create_webhook_app(require_config=True)
