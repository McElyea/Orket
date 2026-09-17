"""Pure ASGI transport keeps the complete request lifetime under its app owner."""
from __future__ import annotations

import asyncio
from contextvars import ContextVar
from typing import Any

from fastapi import FastAPI
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from orket import __version__
from orket.application.services.api_runtime_container import ApiRequestAdmissionClosed
from orket.interfaces.api_runtime_context import get_api_runtime_context


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
        response_started = False

        async def send_response(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
                if scope.get("path", "").startswith("/v1/"):
                    message = dict(message)
                    headers = [(key, value) for key, value in message.get("headers", [])
                               if key.lower() != b"x-orket-version"]
                    message["headers"] = [*headers, (b"x-orket-version", __version__.encode("ascii"))]
            await send(message)

        try:
            await context.run_request(lambda: self._app(scope, receive, send_response))
        except ApiRequestAdmissionClosed:
            await _unavailable(scope, send_response)
        except asyncio.CancelledError:
            if context.accepting_work or response_started:
                raise
            await _unavailable(scope, send_response)


async def _unavailable(scope: Scope, send: Send) -> None:
    if scope["type"] == "websocket":
        await send({"type": "websocket.close", "code": 1001})
        return
    body = b'{"detail":"API runtime is closing."}'
    await send({"type": "http.response.start", "status": 503, "headers": [
        (b"content-type", b"application/json"), (b"content-length", str(len(body)).encode("ascii"))]})
    await send({"type": "http.response.body", "body": body})
