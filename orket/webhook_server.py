"""Standalone Gitea transport; application owns configuration, dispatch and lifetime."""

from __future__ import annotations

import json
from collections.abc import Mapping
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from orket import __version__
from orket.application.services.gitea_webhook_runtime import build_webhook_runtime
from orket.application.services.runtime_input_service import RuntimeInputService
from orket.application.services.webhook_configuration import capture_webhook_configuration
from orket.interfaces.webhook_app_context import WebhookAppContextMiddleware

MAX_BODY_SIZE = 1024 * 1024


class GiteaWebhookPayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    action: str | None = None
    number: int | None = Field(None, gt=0)
    pull_request: dict[str, Any] | None = None
    repository: dict[str, Any] | None = None
    review: dict[str, Any] | None = None
    sender: dict[str, Any] | None = None


class TestWebhookPayload(BaseModel):
    event: str = "test"
    action: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


async def root() -> dict[str, str]:
    return {"service": "Orket Webhook Server", "status": "running", "version": __version__}


async def health(request: Request) -> dict[str, Any]:
    configuration = request.app.state.webhook_runtime.configuration
    return {
        "status": "healthy",
        "rate_limit_scope": "per_application_per_process",
        "webhook_rate_limit_per_minute": configuration.rate_limit,
        "worker_count_hint": configuration.worker_count,
    }


async def _request_body(request: Request) -> bytes:
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_BODY_SIZE:
            raise HTTPException(status_code=413, detail="Payload too large")
        body.extend(chunk)
    return bytes(body)


async def gitea_webhook(
    request: Request,
    x_gitea_event: str | None = Header(None),
    x_gitea_signature: str | None = Header(None),
    x_gitea_delivery: str | None = Header(None),
) -> JSONResponse:
    runtime = request.app.state.webhook_runtime
    if not await runtime.ingress.allow():
        raise HTTPException(status_code=429, detail="Webhook rate limit exceeded", headers={"Retry-After": "60"})
    body = await _request_body(request)
    if not x_gitea_signature:
        await runtime._log_event("webhook", {"message": "Missing webhook signature", "level": "error"})
        raise HTTPException(status_code=401, detail="Missing signature")
    if not runtime.ingress.validate_signature(body, x_gitea_signature):
        await runtime._log_event("webhook", {"message": "Invalid webhook signature", "level": "error"})
        raise HTTPException(status_code=401, detail="Invalid signature")
    try:
        payload = GiteaWebhookPayload.model_validate(json.loads(body)).model_dump(exclude_none=True)
    except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as exc:
        await runtime._log_event(
            "webhook", {"message": f"Failed to parse or validate webhook payload: {exc}", "level": "error"}
        )
        raise HTTPException(status_code=400, detail=f"Invalid payload: {exc}") from exc
    if x_gitea_delivery and x_gitea_delivery.strip():
        delivery = x_gitea_delivery.strip()
        supplied = [
            str(payload[key]).strip()
            for key in ("event_id", "delivery_id", "x_gitea_delivery", "X-Gitea-Delivery")
            if payload.get(key)
        ]
        if any(value != delivery for value in supplied):
            raise HTTPException(status_code=400, detail="Conflicting webhook delivery identifiers")
        payload["event_id"] = delivery
    await runtime._log_event(
        "webhook",
        {
            "message": f"Received Gitea webhook: {x_gitea_event}",
            "level": "info",
            "event": x_gitea_event,
            "repo": (payload.get("repository") or {}).get("full_name"),
            "pr_number": payload.get("number"),
        },
    )
    try:
        result = await runtime._dispatch(str(x_gitea_event or ""), payload)
        return JSONResponse(content=result, status_code=200)
    except Exception as exc:  # transport boundary reports a failed invocation with its context
        await runtime._log_event(
            "webhook",
            {
                "message": f"Webhook handler error: {exc}",
                "level": "error",
                "event_type": x_gitea_event,
                "delivery_id": x_gitea_delivery,
            },
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc


async def test_webhook(
    request: Request,
    req: TestWebhookPayload,
    x_api_key: str | None = Header(None),
    x_webhook_test_token: str | None = Header(None),
) -> JSONResponse:
    runtime = request.app.state.webhook_runtime
    allowed, detail, status = runtime.ingress.validate_test_auth(x_api_key, x_webhook_test_token)
    if not allowed:
        raise HTTPException(status_code=status, detail=detail)
    payload = dict(req.payload)
    if req.action and "action" not in payload:
        payload["action"] = req.action
    await runtime._log_event("webhook", {"message": f"Test webhook received: {req.event}", "level": "info"})
    result = await runtime._dispatch(req.event or "test", payload)
    return JSONResponse(content=result, status_code=200)


def create_webhook_app(
    require_config: bool = True,
    *,
    project_root: Path | None = None,
    environment: Mapping[str, str] | None = None,
    runtime_inputs: RuntimeInputService | None = None,
) -> FastAPI:
    configuration = capture_webhook_configuration(project_root, environment=environment, require_config=require_config)
    started = False

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        nonlocal started
        if started:
            raise RuntimeError("Webhook application lifespan already started; create a new application.")
        started = True
        runtime = await build_webhook_runtime(configuration, runtime_inputs=runtime_inputs)
        app.state.webhook_runtime = runtime
        try:
            yield
        finally:
            await runtime.close()

    app = FastAPI(
        title="Orket Webhook Server",
        description="Handles webhooks from Gitea for PR review automation",
        version=__version__,
        lifespan=lifespan,
    )
    app.state.webhook_runtime = None
    app.add_middleware(WebhookAppContextMiddleware, owner_app=app)
    app.add_api_route("/", root, methods=["GET"])
    app.add_api_route("/health", health, methods=["GET"])
    app.add_api_route("/webhook/gitea", gitea_webhook, methods=["POST"])
    app.add_api_route("/webhook/test", test_webhook, methods=["POST"])
    return app


def start_server(host: str = "127.0.0.1", port: int = 8080) -> None:
    uvicorn.run(create_webhook_app(), host=host, port=port, log_level="info")


if __name__ == "__main__":
    start_server()
