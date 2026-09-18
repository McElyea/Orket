"""ASGI transport admission through an application's shared lifetime owner."""

from __future__ import annotations

import asyncio
import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from orket import __version__
from orket.application.services.application_runtime_lifetime import ApplicationRuntimeLifetime, RequestAdmissionClosed


async def unavailable(scope: Scope, send: Send, *, detail: str) -> None:
    if scope["type"] == "websocket":
        await send({"type": "websocket.close", "code": 1001})
        return
    body = json.dumps({"detail": detail}, separators=(",", ":")).encode()
    await send(
        {
            "type": "http.response.start",
            "status": 503,
            "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode("ascii"))],
        }
    )
    await send({"type": "http.response.body", "body": body})


async def run_owned_asgi(
    owner: ApplicationRuntimeLifetime,
    app: ASGIApp,
    scope: Scope,
    receive: Receive,
    send: Send,
    *,
    unavailable_detail: str,
    version_header: bool = False,
) -> None:
    response_started = False

    async def send_response(message: Message) -> None:
        nonlocal response_started
        if message["type"] == "http.response.start":
            response_started = True
            if version_header and scope.get("path", "").startswith("/v1/"):
                message = dict(message)
                headers = [
                    (key, value) for key, value in message.get("headers", []) if key.lower() != b"x-orket-version"
                ]
                message["headers"] = [*headers, (b"x-orket-version", __version__.encode("ascii"))]
        await send(message)

    try:
        await owner.run_request(lambda: app(scope, receive, send_response))
    except RequestAdmissionClosed:
        await unavailable(scope, send_response, detail=unavailable_detail)
    except asyncio.CancelledError:
        if owner.accepting_work or response_started:
            raise
        await unavailable(scope, send_response, detail=unavailable_detail)
