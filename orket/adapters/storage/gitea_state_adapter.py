from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from orket.adapters.storage.gitea_http_client import GiteaHTTPClient
from orket.adapters.storage.gitea_lease_manager import GiteaLeaseManager
from orket.adapters.storage.gitea_state_errors import (
    GiteaAdapterAuthError,
    GiteaAdapterConflictError,
    GiteaAdapterError,
    GiteaAdapterNetworkError,
    GiteaAdapterRateLimitError,
    GiteaAdapterTimeoutError,
)
from orket.adapters.storage.gitea_state_models import (
    build_event_comment,
    decode_snapshot,
    parse_event_comment,
)
from orket.adapters.storage.gitea_state_transitioner import GiteaStateTransitioner
from orket.core.contracts.state_backend import StateBackendContract


class GiteaStateAdapter(StateBackendContract):
    """Experimental state backend adapter for Gitea issues."""

    def __init__(
        self,
        *,
        base_url: str,
        owner: str,
        repo: str,
        token: str,
        ready_label: str = "status/ready",
        timeout_seconds: float = 20.0,
        max_retries: int = 2,
        backoff_base_seconds: float = 0.1,
        backoff_max_seconds: float = 1.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.owner = owner
        self.repo = repo
        self.ready_label = ready_label
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(0, int(max_retries))
        self.backoff_base_seconds = max(0.0, float(backoff_base_seconds))
        self.backoff_max_seconds = max(self.backoff_base_seconds, float(backoff_max_seconds))
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/json",
        }

        self.http = GiteaHTTPClient(self)
        self.leases = GiteaLeaseManager(self)
        self.transitions = GiteaStateTransitioner(self)

    def __getattr__(self, name: str) -> Any:
        delegated = {
            "_request_response": self.http.request_response,
            "_request_json": self.http.request_json,
            "_request_response_with_retry": self.http.request_response_with_retry,
            "acquire_lease": self.leases.acquire_lease,
            "renew_lease": self.leases.renew_lease,
            "transition_state": self.transitions.transition_state,
            "release_or_fail": self.transitions.release_or_fail,
            "_validate_transition": self.transitions.validate_transition,
            "_parse_iso": self.transitions.parse_iso,
            "_now_utc": self.transitions.now_utc,
            "_classify_http_error": self.http.classify_http_error,
            "_log_failure": self.http.log_failure,
            "_extract_card_id": self.http.extract_card_id,
        }
        target = delegated.get(name)
        if target is not None:
            return target
        raise AttributeError(name)

    @property
    def _repo_api(self) -> str:
        return f"{self.base_url}/api/v1/repos/{self.owner}/{self.repo}"

    async def _request_response(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ):
        return await self.http.request_response(
            method,
            path,
            params=params,
            payload=payload,
            extra_headers=extra_headers,
        )

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        return await self.http.request_json(
            method,
            path,
            params=params,
            payload=payload,
            extra_headers=extra_headers,
        )

    async def _request_response_with_retry(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ):
        return await self.http.request_response_with_retry(
            method,
            path,
            params=params,
            payload=payload,
            extra_headers=extra_headers,
        )

    async def acquire_lease(
        self,
        card_id: str,
        *,
        owner_id: str,
        lease_seconds: int,
    ) -> Optional[Dict[str, Any]]:
        return await self.leases.acquire_lease(card_id, owner_id=owner_id, lease_seconds=lease_seconds)

    async def renew_lease(
        self,
        card_id: str,
        *,
        owner_id: str,
        lease_seconds: int,
    ) -> Optional[Dict[str, Any]]:
        return await self.leases.renew_lease(card_id, owner_id=owner_id, lease_seconds=lease_seconds)

    async def transition_state(
        self,
        card_id: str,
        *,
        from_state: str,
        to_state: str,
        reason: Optional[str] = None,
    ) -> None:
        await self.transitions.transition_state(card_id, from_state=from_state, to_state=to_state, reason=reason)

    async def release_or_fail(
        self,
        card_id: str,
        *,
        final_state: str,
        error: Optional[str] = None,
    ) -> None:
        await self.transitions.release_or_fail(card_id, final_state=final_state, error=error)

    @staticmethod
    def _validate_transition(*, from_state: str, to_state: str) -> None:
        GiteaStateTransitioner.validate_transition(from_state=from_state, to_state=to_state)

    @staticmethod
    def _parse_iso(raw: Optional[str]) -> Optional[datetime]:
        return GiteaStateTransitioner.parse_iso(raw)

    @staticmethod
    def _now_utc():
        return GiteaStateTransitioner.now_utc()

    @staticmethod
    def _classify_http_error(*, status_code: Optional[int], exc: Exception) -> GiteaAdapterError:
        return GiteaHTTPClient.classify_http_error(status_code=status_code, exc=exc)

    @staticmethod
    def _extract_card_id(path: str) -> str:
        return GiteaHTTPClient.extract_card_id(path)

    @staticmethod
    def _log_failure(failure_class: str, **fields: Any) -> None:
        GiteaHTTPClient.log_failure(failure_class, **fields)

    async def fetch_ready_cards(self, *, limit: int = 1) -> List[Dict[str, Any]]:
        payload = await self._request_json(
            "GET",
            "/issues",
            params={"state": "open", "labels": self.ready_label, "limit": max(1, int(limit))},
        )
        if not isinstance(payload, list):
            return []
        cards: List[Dict[str, Any]] = []
        for issue in payload:
            if not isinstance(issue, dict):
                continue
            try:
                snapshot = decode_snapshot(str(issue.get("body") or ""))
            except (ValueError, ValidationError):
                continue
            cards.append(
                {
                    "card_id": snapshot.card_id,
                    "issue_number": issue.get("number"),
                    "state": snapshot.state,
                    "version": snapshot.version,
                    "lease": snapshot.lease.model_dump(),
                    "metadata": snapshot.metadata,
                }
            )
        return cards

    async def append_event(
        self,
        card_id: str,
        *,
        event_type: str,
        payload: Dict[str, Any],
    ) -> None:
        issue_number = int(card_id)
        idempotency_key = str(payload.get("idempotency_key") or "").strip() or None
        if idempotency_key and await self._event_exists(issue_number, idempotency_key=idempotency_key):
            return
        comment = build_event_comment(event_type, payload, idempotency_key=idempotency_key)
        await self._request_json("POST", f"/issues/{issue_number}/comments", payload={"body": comment})

    async def _event_exists(self, issue_number: int, *, idempotency_key: str) -> bool:
        payload = await self._request_json("GET", f"/issues/{issue_number}/comments")
        if not isinstance(payload, list):
            return False
        for entry in payload:
            if not isinstance(entry, dict):
                continue
            body = str(entry.get("body") or "")
            if not body.startswith("[ORKET_EVENT_V1]"):
                continue
            try:
                event = parse_event_comment(body)
            except (ValueError, ValidationError):
                continue
            if str(event.idempotency_key or "").strip() == idempotency_key:
                return True
        return False


__all__ = [
    "GiteaAdapterAuthError",
    "GiteaAdapterConflictError",
    "GiteaAdapterError",
    "GiteaAdapterNetworkError",
    "GiteaAdapterRateLimitError",
    "GiteaAdapterTimeoutError",
    "GiteaStateAdapter",
]
