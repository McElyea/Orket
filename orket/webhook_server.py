"""
FastAPI Webhook Server for Gitea Integration

Receives webhook events from Gitea and routes them to appropriate handlers.
Includes HMAC signature validation for security.
"""
from __future__ import annotations
import hmac
import hashlib
import os
import json
import asyncio
import time
from collections import deque
from typing import Dict, Any, Optional
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import uvicorn

from orket import __version__
from orket.services.gitea_webhook_handler import GiteaWebhookHandler
from orket.logging import log_event

load_dotenv()

app = FastAPI(
    title="Orket Webhook Server",
    description="Handles webhooks from Gitea for PR review automation",
    version=__version__
)

# Initialize webhook handler
webhook_handler = GiteaWebhookHandler(
    gitea_url=os.getenv("GITEA_URL", "http://localhost:3000"),
    workspace=Path.cwd()
)

# Webhook secret for HMAC validation (set in Gitea webhook config)
_webhook_secret_raw = os.getenv("GITEA_WEBHOOK_SECRET", "")
if not _webhook_secret_raw.strip():
    raise RuntimeError(
        "GITEA_WEBHOOK_SECRET environment variable is not set. "
        "Configure it before starting the webhook server."
    )
WEBHOOK_SECRET = _webhook_secret_raw.encode()


class SlidingWindowRateLimiter:
    """Simple per-process sliding-window limiter."""

    def __init__(self, limit: int, window_seconds: int = 60):
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
    if not WEBHOOK_SECRET:
        log_event(
            "webhook",
            {"message": "GITEA_WEBHOOK_SECRET not set. Authentication disabled.", "level": "error"},
            workspace=Path.cwd(),
        )
        return False  # Reject if not configured

    expected_signature = hmac.new(
        WEBHOOK_SECRET,
        payload,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(signature, expected_signature)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "Orket Webhook Server",
        "status": "running",
        "version": __version__
    }


@app.get("/health")
async def health():
    """Kubernetes-style health check."""
    return {"status": "healthy"}


from pydantic import BaseModel, Field

class GiteaWebhookPayload(BaseModel):
    action: Optional[str] = None
    number: Optional[int] = Field(None, gt=0)
    pull_request: Optional[Dict[str, Any]] = None
    repository: Optional[Dict[str, Any]] = None
    review: Optional[Dict[str, Any]] = None
    sender: Optional[Dict[str, Any]] = None


class TestWebhookPayload(BaseModel):
    event: str = "test"
    action: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)

@app.post("/webhook/gitea")
async def gitea_webhook(
    request: Request,
    x_gitea_event: str = Header(None),
    x_gitea_signature: str = Header(None)
):
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

    # Validate signature
    if x_gitea_signature:
        if not validate_signature(body, x_gitea_signature):
            log_event("webhook", {"message": "Invalid webhook signature", "level": "error"}, workspace=Path.cwd())
            raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse and validate JSON payload
    try:
        payload_data = json.loads(body)
        payload = GiteaWebhookPayload.model_validate(payload_data)
    except Exception as e:
        log_event(
            "webhook",
            {"message": f"Failed to parse or validate webhook payload: {e}", "level": "error"},
            workspace=Path.cwd(),
        )
        raise HTTPException(status_code=400, detail=f"Invalid payload: {e}")

    # Log webhook event
    log_event("webhook", {
        "message": f"Received Gitea webhook: {x_gitea_event}",
        "level": "info",
        "event": x_gitea_event,
        "repo": payload.repository.get("full_name") if payload.repository else None,
        "pr_number": payload.number,
    }, workspace=Path.cwd())

    # Route to handler
    try:
        result = await webhook_handler.handle_webhook(x_gitea_event, payload.model_dump())
        return JSONResponse(content=result, status_code=200)
    except Exception as e:
        log_event("webhook", {"message": f"Webhook handler error: {e}", "level": "error"}, workspace=Path.cwd())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/webhook/test")
async def test_webhook(req: TestWebhookPayload):
    """
    Test endpoint for manual webhook testing (no signature validation).

    Usage:
        curl -X POST http://localhost:8080/webhook/test \
             -H "Content-Type: application/json" \
             -d '{"event": "pull_request_review", "action": "approved"}'
    """
    event_type = req.event or "test"
    log_event("webhook", {"message": f"Test webhook received: {event_type}", "level": "info"}, workspace=Path.cwd())

    handler_payload = req.payload or {}
    if req.action and "action" not in handler_payload:
        handler_payload["action"] = req.action
    result = await webhook_handler.handle_webhook(event_type, handler_payload)
    return JSONResponse(content=result, status_code=200)


def start_server(host: str = "0.0.0.0", port: int = 8080):
    """
    Start the webhook server.

    Args:
        host: Host to bind to (default: 0.0.0.0 for all interfaces)
        port: Port to bind to (default: 8080)
    """
    log_event("webhook_server", {"message": f"Starting webhook server on {host}:{port}", "level": "info"}, workspace=Path.cwd())

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )


if __name__ == "__main__":
    # Start server on port 8080
    start_server()
