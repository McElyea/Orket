from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI

_API_RUNTIME_CONTEXT_STATE_KEY = "api_runtime_context"


@dataclass
class ApiAppRuntimeContext:
    project_root: Path
    api_runtime_host: Any | None = None
    engine: Any | None = None
    stream_bus: Any | None = None
    interaction_manager: Any | None = None
    extension_manager: Any | None = None
    extension_runtime_service: Any | None = None


def get_api_runtime_context(app: FastAPI) -> ApiAppRuntimeContext | None:
    context = getattr(app.state, _API_RUNTIME_CONTEXT_STATE_KEY, None)
    return context if isinstance(context, ApiAppRuntimeContext) else None


def set_api_runtime_context(app: FastAPI, context: ApiAppRuntimeContext) -> ApiAppRuntimeContext:
    context.project_root = Path(context.project_root).resolve()
    app.state.project_root = context.project_root
    setattr(app.state, _API_RUNTIME_CONTEXT_STATE_KEY, context)
    return context
