from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Optional

import httpx

from .gitea_state_errors import (
    GiteaAdapterAuthError,
    GiteaAdapterConflictError,
    GiteaAdapterError,
    GiteaAdapterNetworkError,
    GiteaAdapterRateLimitError,
    GiteaAdapterTimeoutError,
)

logger = logging.getLogger("orket.gitea_state_adapter")


class GiteaHTTPClient:
    """HTTP request and retry handling for Gitea state operations."""

    def __init__(self, adapter: Any) -> None:
        self.adapter = adapter

    async def request_response(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        url = f"{self.adapter._repo_api}{path}"
        headers = dict(self.adapter.headers)
        if extra_headers:
            headers.update(extra_headers)
        try:
            async with httpx.AsyncClient(timeout=self.adapter.timeout_seconds) as client:
                response = await client.request(method, url, headers=headers, params=params, json=payload)
                response.raise_for_status()
                return response
        except httpx.TimeoutException as exc:
            self.log_failure(
                "timeout",
                operation=f"{method} {path}",
                card_id=self.extract_card_id(path),
                error=str(exc),
            )
            raise GiteaAdapterTimeoutError(str(exc)) from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            err = self.classify_http_error(status_code=status_code, exc=exc)
            self.log_failure(
                "http_status",
                operation=f"{method} {path}",
                card_id=self.extract_card_id(path),
                status_code=status_code,
                error=str(exc),
            )
            raise err from exc
        except httpx.RequestError as exc:
            self.log_failure(
                "network",
                operation=f"{method} {path}",
                card_id=self.extract_card_id(path),
                error=str(exc),
            )
            raise GiteaAdapterNetworkError(str(exc)) from exc

    async def request_json(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        response = await self.adapter._request_response_with_retry(
            method,
            path,
            params=params,
            payload=payload,
            extra_headers=extra_headers,
        )
        if not response.text.strip():
            return None
        return response.json()

    async def request_response_with_retry(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        attempts = 0
        while True:
            try:
                return await self.adapter._request_response(
                    method,
                    path,
                    params=params,
                    payload=payload,
                    extra_headers=extra_headers,
                )
            except (GiteaAdapterTimeoutError, GiteaAdapterNetworkError, GiteaAdapterRateLimitError):
                if attempts >= self.adapter.max_retries:
                    raise
                delay = min(self.adapter.backoff_max_seconds, self.adapter.backoff_base_seconds * (2**attempts))
                await asyncio.sleep(delay)
                attempts += 1

    @staticmethod
    def classify_http_error(*, status_code: Optional[int], exc: Exception) -> GiteaAdapterError:
        if status_code == 429:
            return GiteaAdapterRateLimitError(str(exc))
        if status_code in {401, 403}:
            return GiteaAdapterAuthError(str(exc))
        if status_code in {409, 412}:
            return GiteaAdapterConflictError(str(exc))
        return GiteaAdapterError(str(exc))

    @staticmethod
    def extract_card_id(path: str) -> str:
        parts = [segment for segment in str(path or "").split("/") if segment]
        if len(parts) >= 2 and parts[0] == "issues":
            return str(parts[1])
        return ""

    @staticmethod
    def log_failure(failure_class: str, **fields: Any) -> None:
        record = {
            "event": "gitea_state_adapter_failure",
            "backend": "gitea",
            "failure_class": failure_class,
            **fields,
        }
        logger.warning(json.dumps(record, ensure_ascii=False))
