from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from orket.application.services.api_runtime_container import ApiRuntimeContainer

_API_RUNTIME_CONTEXT_STATE_KEY = "api_runtime_context"

ApiAppRuntimeContext = ApiRuntimeContainer


def get_api_runtime_context(app: FastAPI) -> ApiAppRuntimeContext | None:
    context = getattr(app.state, _API_RUNTIME_CONTEXT_STATE_KEY, None)
    return context if isinstance(context, ApiAppRuntimeContext) else None


def set_api_runtime_context(app: FastAPI, context: ApiAppRuntimeContext) -> ApiAppRuntimeContext:
    if not Path(context.project_root).is_absolute():
        raise ValueError("E_API_RUNTIME_ROOT_ABSOLUTE_REQUIRED")
    app.state.project_root = context.project_root
    setattr(app.state, _API_RUNTIME_CONTEXT_STATE_KEY, context)
    return context
