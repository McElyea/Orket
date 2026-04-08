"""
FastAPI Webhook Server for Gitea Integration

Receives webhook events from Gitea and routes them to appropriate handlers.
Includes HMAC signature validation for security.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import time
from collections import deque
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError

from orket import __version__
from orket.adapters.vcs.gitea_webhook_handler import GiteaWebhookHandler
from orket.logging import log_event
from orket.settings import load_env

app = FastAPI(
    title="Orket Webhook Server",
    description="Handles webhooks from Gitea for PR review automation",
    version=__version__,
)

WEBHOOK_SECRET: bytes | None = None


class _WebhookHandlerProxy:
    def __init__(self) -> None:
        self._handler: GiteaWebhookHandler | None = None

    def _create_handler(self) -> GiteaWebhookHandler:
        return GiteaWebhookHandler(
            gitea_url=os.getenv("GITEA_URL", "https://localhost:3000"),
            workspace=Path.cwd(),
            allow_insecure=_is_truthy(os.getenv("ORKET_GITEA_ALLOW_INSECURE")),
        )

    def _get(self) -> GiteaWebhookHandler:
        if self._handler is None:
            self._handler = self._create_handler()
        return self._handler

    def reset(self) -> None:
        self._handler = None

    async def handle_webhook(self, event_type: str, payload: dict[str, Any]) -> dict[str, str]:
        return await self._get().handle_webhook(event_type, payload)

    async def close(self) -> None:
        if self._handler is not None:
            await self._handler.close()
            self._handler = None


webhook_handler = _WebhookHandlerProxy()
app.add_event_handler("shutdown", webhook_handler.close)


def _resolve_webhook_secret(required: bool = False) -> bytes | None:
    global WEBHOOK_SECRET
    raw = os.getenv("GITEA_WEBHOOK_SECRET", "")
    if raw.strip():
        WEBHOOK_SECRET = raw.encode()
        return WEBHOOK_SECRET
    WEBHOOK_SECRET = None
    if required:
        raise RuntimeError(
            "GITEA_WEBHOOK_SECRET environment variable is not set. Configure it before starting the webhook server."
        )
    return None


def _validate_required_webhook_environment() -> None:
    missing: list[str] = []
    if not os.getenv("GITEA_WEBHOOK_SECRET", "").strip():
        missing.append("GITEA_WEBHOOK_SECRET")
    if not os.getenv("GITEA_ADMIN_PASSWORD", "").strip():
        missing.append("GITEA_ADMIN_PASSWORD")
    if missing:
        missing_list = ", ".join(missing)
        raise RuntimeError(
            f"Missing required webhook environment variable(s): {missing_list}. "
            "Configure them in environment or .env before starting the webhook server."
        )


def _is_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _validate_test_webhook_auth(
    x_api_key: str | None, x_webhook_test_token: str | None
) -> tuple[bool, str | None, int]:
    """
    Validate auth for /webhook/test.
    Priority:
    1) ORKET_WEBHOOK_TEST_TOKEN via X-Webhook-Test-Token
    2) ORKET_API_KEY via X-API-Key
    """
    test_token = os.getenv("ORKET_WEBHOOK_TEST_TOKEN", "").strip()
    api_key = os.getenv("ORKET_API_KEY", "").strip()

    if test_token:
        if x_webhook_test_token == test_token:
            return True, None, 200
        return False, "Invalid test webhook token", 401

    if api_key:
        if x_api_key == api_key:
            return True, None, 200
        return False, "Invalid API key", 401

    return False, "Test webhook auth not configured", 403


class SlidingWindowRateLimiter:
    """Simple per-process sliding-window limiter."""

    def __init__(self, limit: int, window_seconds: int = 60) -> None:
        self.limit = max(1, int(limit))
        self.window_seconds = window_seconds
        self._events: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def allow(self) -> bool:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        async with self._lock:
            while self._events and self._events[0] < cutoff:
                self._events.popleft()
            if len(self._events) >= self.limit:
                return False
            self._events.append(now)
            return True


_rate_limit_raw = os.getenv("ORKET_RATE_LIMIT", "60")
try:
    _rate_limit = int(_rate_limit_raw)
except ValueError:
    _rate_limit = 60
webhook_rate_limiter = SlidingWindowRateLimiter(_rate_limit, window_seconds=60)


def validate_signature(payload: bytes, signature: str) -> bool:
    """
    Validate HMAC-SHA256 signature from Gitea webhook.

    Args:
        payload: Raw request body bytes
        signature: Signature from X-Gitea-Signature header

    Returns:
        True if signature is valid, False otherwise
    """
    secret = _resolve_webhook_secret(required=False)
    if not secret:
        log_event(
            "webhook",
            {"message": "GITEA_WEBHOOK_SECRET not set. All webhooks will be rejected.", "level": "error"},
            workspace=Path.cwd(),
        )
        return False  # Reject if not configured

    expected_signature = hmac.new(secret, payload, hashlib.sha256).hexdigest()

    return hmac.compare_digest(signature, expected_signature)


@app.get("/")
async def root() -> dict[str, str]:
    """Health check endpoint."""
    return {"service": "Orket Webhook Server", "status": "running", "version": __version__}


@app.get("/health")
async def health() -> dict[str, str]:
    """Kubernetes-style health check."""
    return {"status": "healthy"}


class GiteaWebhookPayload(BaseModel):
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


@app.post("/webhook/gitea")
async def gitea_webhook(
    request: Request,
    x_gitea_event: str | None = Header(None),
    x_gitea_signature: str | None = Header(None),
) -> JSONResponse:
    """
    Main Gitea webhook endpoint.
    """
    if not await webhook_rate_limiter.allow():
        raise HTTPException(
            status_code=429,
            detail="Webhook rate limit exceeded",
            headers={"Retry-After": "60"},
        )

    # Size limit: 1MB
    MAX_SIZE = 1024 * 1024
    body = await request.body()
    if len(body) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="Payload too large")

    # Signature is mandatory for trusted webhook ingress.
    if not x_gitea_signature:
        log_event("webhook", {"message": "Missing webhook signature", "level": "error"}, workspace=Path.cwd())
        raise HTTPException(status_code=401, detail="Missing signature")

    if not validate_signature(body, x_gitea_signature):
        log_event("webhook", {"message": "Invalid webhook signature", "level": "error"}, workspace=Path.cwd())
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse and validate JSON payload
    try:
        payload_data = json.loads(body)
        payload = GiteaWebhookPayload.model_validate(payload_data)
    except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as exc:
        log_event(
            "webhook",
            {"message": f"Failed to parse or validate webhook payload: {exc}", "level": "error"},
            workspace=Path.cwd(),
        )
        raise HTTPException(status_code=400, detail=f"Invalid payload: {exc}") from exc

    # Log webhook event
    log_event(
        "webhook",
        {
            "message": f"Received Gitea webhook: {x_gitea_event}",
            "level": "info",
            "event": x_gitea_event,
            "repo": payload.repository.get("full_name") if payload.repository else None,
            "pr_number": payload.number,
        },
        workspace=Path.cwd(),
    )

    # Route to handler
    try:
        result = await webhook_handler.handle_webhook(str(x_gitea_event or ""), payload.model_dump())
        return JSONResponse(content=result, status_code=200)
    except (RuntimeError, ValueError, TypeError, KeyError, OSError) as exc:
        log_event("webhook", {"message": f"Webhook handler error: {exc}", "level": "error"}, workspace=Path.cwd())
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/webhook/test")
async def test_webhook(
    req: TestWebhookPayload,
    x_api_key: str | None = Header(None),
    x_webhook_test_token: str | None = Header(None),
) -> JSONResponse:
    """
    Test endpoint for manual webhook testing (no signature validation).

    Usage:
        curl -X POST http://localhost:8080/webhook/test \
             -H "Content-Type: application/json" \
             -d '{"event": "pull_request_review", "action": "approved"}'
    """
    enabled = _is_truthy(os.getenv("ORKET_ENABLE_WEBHOOK_TEST_ENDPOINT"))
    if not enabled:
        raise HTTPException(status_code=403, detail="Test webhook endpoint disabled")

    allowed, detail, status_code = _validate_test_webhook_auth(x_api_key, x_webhook_test_token)
    if not allowed:
        raise HTTPException(status_code=status_code, detail=detail)

    event_type = req.event or "test"
    log_event("webhook", {"message": f"Test webhook received: {event_type}", "level": "info"}, workspace=Path.cwd())

    handler_payload = req.payload or {}
    if req.action and "action" not in handler_payload:
        handler_payload["action"] = req.action
    result = await webhook_handler.handle_webhook(event_type, handler_payload)
    return JSONResponse(content=result, status_code=200)


def start_server(host: str = "127.0.0.1", port: int = 8080) -> None:
    """
    Start the webhook server.

    Args:
        host: Host to bind to (default: 127.0.0.1 for local-only binding)
        port: Port to bind to (default: 8080)
    """
    log_event(
        "webhook_server",
        {"message": f"Starting webhook server on {host}:{port}", "level": "info"},
        workspace=Path.cwd(),
    )
    create_webhook_app(require_config=True)

    uvicorn.run(app, host=host, port=port, log_level="info")


def create_webhook_app(require_config: bool = False) -> FastAPI:
    if require_config:
        load_env()
        _validate_required_webhook_environment()
        _resolve_webhook_secret(required=True)
        webhook_handler._get()
    return app


# Startup posture logging for operator visibility.
if _is_truthy(os.getenv("ORKET_ENABLE_WEBHOOK_TEST_ENDPOINT")):
    _has_test_token = bool(os.getenv("ORKET_WEBHOOK_TEST_TOKEN", "").strip())
    _has_api_key = bool(os.getenv("ORKET_API_KEY", "").strip())
    log_event(
        "webhook_security_posture",
        {
            "test_endpoint_enabled": True,
            "test_token_configured": _has_test_token,
            "api_key_configured": _has_api_key,
        },
        workspace=Path.cwd(),
    )
    if not _has_test_token and not _has_api_key:
        log_event(
            "webhook_security_warning",
            {"message": "ORKET_ENABLE_WEBHOOK_TEST_ENDPOINT is true but no test auth secret is configured."},
            workspace=Path.cwd(),
        )


if __name__ == "__main__":
    # Start server on port 8080
    start_server()
