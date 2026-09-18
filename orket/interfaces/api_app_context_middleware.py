"""Pure ASGI transport keeps the complete request lifetime under its app owner."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from fastapi import FastAPI
from starlette.types import ASGIApp, Receive, Scope, Send

from orket.interfaces.api_runtime_context import get_api_runtime_context
from orket.interfaces.application_request_lifetime import run_owned_asgi


class ApiAppContextMiddleware:
    def __init__(self, app: ASGIApp, *, owner_app: FastAPI, active_app: ContextVar[Any]) -> None:
        self._app, self._owner_app, self._active_app = app, owner_app, active_app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        token = self._active_app.set(self._owner_app)
        try:
            if scope["type"] in {"http", "websocket"}:
                await self._request(scope, receive, send)
            else:
                await self._app(scope, receive, send)
        finally:
            self._active_app.reset(token)

    async def _request(self, scope: Scope, receive: Receive, send: Send) -> None:
        context = get_api_runtime_context(self._owner_app)
        if context is None:
            raise RuntimeError("API app runtime context is missing.")
        await run_owned_asgi(
            context, self._app, scope, receive, send, unavailable_detail="API runtime is closing.", version_header=True
        )
