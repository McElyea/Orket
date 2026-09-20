"""Bind API transport callbacks without constructing application runtime resources."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from contextvars import ContextVar
from typing import Any

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from orket.interfaces.api_app_context_middleware import ApiAppContextMiddleware
from orket.interfaces.routers.streaming import register_streaming_routes
from orket.runtime.cors_config import resolve_cors_config


def register_api_transport(
    app: FastAPI, *, environment: Mapping[str, str], active_app: ContextVar[Any],
    router: APIRouter, health: Callable[..., Any], api_key_name: str,
    authentication_getter: Callable[[], Any], runtime_host_getter: Callable[[], Any],
    interaction_manager_getter: Callable[[], Any], runtime_state_getter: Callable[[], Any],
    events_getter: Callable[[], Any],
) -> None:
    config = resolve_cors_config(environment)
    app.add_middleware(CORSMiddleware, allow_origins=config.allow_origins, allow_methods=config.allow_methods,
                       allow_headers=config.allow_headers, allow_credentials=config.allow_credentials)
    app.add_middleware(ApiAppContextMiddleware, owner_app=app, active_app=active_app)
    app.add_api_route("/health", health, methods=["GET"])
    app.include_router(router)
    register_streaming_routes(app, api_key_name=api_key_name, authentication_getter=authentication_getter,
        runtime_host_getter=runtime_host_getter, interaction_manager_getter=interaction_manager_getter,
        runtime_state_getter=runtime_state_getter, events_getter=events_getter)
