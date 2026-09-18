"""Bind each webhook ASGI invocation to the owner created by its app lifespan."""

from __future__ import annotations

from fastapi import FastAPI
from starlette.types import ASGIApp, Receive, Scope, Send

from orket.interfaces.application_request_lifetime import run_owned_asgi, unavailable


class WebhookAppContextMiddleware:
    def __init__(self, app: ASGIApp, *, owner_app: FastAPI) -> None:
        self._app, self._owner_app = app, owner_app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in {"http", "websocket"}:
            await self._app(scope, receive, send)
            return
        owner = self._owner_app.state.webhook_runtime
        if owner is None:
            await unavailable(scope, send, detail="Webhook runtime is not initialized.")
            return
        await run_owned_asgi(owner, self._app, scope, receive, send, unavailable_detail="Webhook runtime is closing.")
