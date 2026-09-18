"""Transport entrypoints request application authorization before composition."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from orket.runtime.policy.composition import CompositionConfig, require_composition_capability


def create_api_app(config: CompositionConfig | None = None) -> Any:
    require_composition_capability("api.http.v1", config)
    from orket.interfaces.api import create_api_app as build_api_app

    return build_api_app(project_root=config.project_root if config else None)


def create_cli_runtime(config: CompositionConfig | None = None) -> Callable[..., Any]:
    require_composition_capability("cli.runtime", config)
    from orket.interfaces.cli import run_cli

    return run_cli


def create_webhook_app(config: CompositionConfig | None = None) -> Any:
    require_composition_capability("webhook.gitea.v1", config)
    from orket.webhook_server import create_webhook_app as build_webhook_app

    return build_webhook_app(require_config=True)
