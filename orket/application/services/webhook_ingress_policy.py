"""Application-owned authentication and per-instance admission observations."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import math
from collections import deque
from collections.abc import Callable

from orket.application.services.webhook_configuration import WebhookConfiguration


class WebhookIngressPolicy:
    def __init__(self, configuration: WebhookConfiguration, *, monotonic: Callable[[], float]) -> None:
        self.configuration = configuration
        self._monotonic = monotonic
        self._events: deque[float] = deque()
        self._lock = asyncio.Lock()
        self._last_observation: float | None = None

    def validate_signature(self, payload: bytes, signature: str) -> bool:
        secret = self.configuration.secret
        if not secret.strip():
            return False
        expected = hmac.new(secret, payload, hashlib.sha256).hexdigest()
        # Gitea sends bare hex. Preserve the previously admitted prefixed form.
        supplied = signature.removeprefix("sha256=")
        return hmac.compare_digest(supplied.encode(), expected.encode())

    def validate_test_auth(self, api_key: str | None, token: str | None) -> tuple[bool, str | None, int]:
        if not self.configuration.test_enabled:
            return False, "Test webhook endpoint disabled", 403
        for expected, supplied, message in (
            (self.configuration.test_token, token, "Invalid test webhook token"),
            (self.configuration.api_key, api_key, "Invalid API key"),
        ):
            if expected:
                if supplied is not None and hmac.compare_digest(supplied.encode(), expected.encode()):
                    return True, None, 200
                return False, message, 401
        return False, "Test webhook auth not configured", 403

    async def allow(self) -> bool:
        async with self._lock:
            now = self._monotonic()
            if not math.isfinite(now) or (self._last_observation is not None and now < self._last_observation):
                raise ValueError("Webhook admission clock must be finite and nondecreasing.")
            self._last_observation = now
            while self._events and self._events[0] < now - 60:
                self._events.popleft()
            if len(self._events) >= self.configuration.rate_limit:
                return False
            self._events.append(now)
            return True
