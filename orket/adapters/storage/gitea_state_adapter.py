from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import json
import logging
from typing import Any, Dict, List, Optional

import httpx

from orket.adapters.storage.gitea_state_models import (
    CardSnapshot,
    LeaseInfo,
    build_event_comment,
    decode_snapshot,
    encode_snapshot,
    parse_event_comment,
)
from orket.core.contracts.state_backend import StateBackendContract
from orket.core.domain.state_machine import StateMachine, StateMachineError
from orket.schema import CardStatus, CardType, WaitReason


logger = logging.getLogger("orket.gitea_state_adapter")


class GiteaAdapterError(RuntimeError):
    pass


class GiteaAdapterRateLimitError(GiteaAdapterError):
    pass


class GiteaAdapterAuthError(GiteaAdapterError):
    pass


class GiteaAdapterConflictError(GiteaAdapterError):
    pass


class GiteaAdapterTimeoutError(GiteaAdapterError):
    pass


class GiteaAdapterNetworkError(GiteaAdapterError):
    pass


class GiteaStateAdapter(StateBackendContract):
    """
    Experimental state backend adapter for Gitea issues.

    P1 slices:
    - Implemented: fetch_ready_cards, append_event, acquire_lease (CAS + lease epoch)
    - Pending: retry/backoff policy and multi-runner hardening flows
    """

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
    ) -> httpx.Response:
        url = f"{self._repo_api}{path}"
        headers = dict(self.headers)
        if extra_headers:
            headers.update(extra_headers)
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    json=payload,
                )
                response.raise_for_status()
                return response
        except httpx.TimeoutException as exc:
            self._log_failure(
                "timeout",
                operation=f"{method} {path}",
                error=str(exc),
            )
            raise GiteaAdapterTimeoutError(str(exc)) from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            err = self._classify_http_error(status_code=status_code, exc=exc)
            self._log_failure(
                "http_status",
                operation=f"{method} {path}",
                status_code=status_code,
                error=str(exc),
            )
            raise err from exc
        except httpx.RequestError as exc:
            self._log_failure(
                "network",
                operation=f"{method} {path}",
                error=str(exc),
            )
            raise GiteaAdapterNetworkError(str(exc)) from exc

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        response = await self._request_response_with_retry(
            method,
            path,
            params=params,
            payload=payload,
            extra_headers=extra_headers,
        )
        if not response.text.strip():
            return None
        return response.json()

    async def _request_response_with_retry(
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
                return await self._request_response(
                    method,
                    path,
                    params=params,
                    payload=payload,
                    extra_headers=extra_headers,
                )
            except (GiteaAdapterTimeoutError, GiteaAdapterNetworkError, GiteaAdapterRateLimitError):
                if attempts >= self.max_retries:
                    raise
                delay = min(self.backoff_max_seconds, self.backoff_base_seconds * (2**attempts))
                await asyncio.sleep(delay)
                attempts += 1

    async def fetch_ready_cards(self, *, limit: int = 1) -> List[Dict[str, Any]]:
        payload = await self._request_json(
            "GET",
            "/issues",
            params={
                "state": "open",
                "labels": self.ready_label,
                "limit": max(1, int(limit)),
            },
        )
        if not isinstance(payload, list):
            return []
        cards: List[Dict[str, Any]] = []
        for issue in payload:
            if not isinstance(issue, dict):
                continue
            body = str(issue.get("body") or "")
            try:
                snapshot = decode_snapshot(body)
            except Exception:
                # Ignore non-Orket issues even if they have a ready label.
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

    async def acquire_lease(
        self,
        card_id: str,
        *,
        owner_id: str,
        lease_seconds: int,
    ) -> Optional[Dict[str, Any]]:
        issue_number = int(card_id)
        issue_response = await self._request_response_with_retry("GET", f"/issues/{issue_number}")
        issue = issue_response.json()
        if not isinstance(issue, dict):
            return None

        try:
            snapshot = decode_snapshot(str(issue.get("body") or ""))
        except Exception:
            return None
        etag = issue_response.headers.get("ETag")
        now = self._now_utc()
        current_owner = str(snapshot.lease.owner_id or "").strip()
        expires_at = self._parse_iso(snapshot.lease.expires_at)
        lease_active = expires_at is not None and expires_at > now

        # Idempotent duplicate acquire by same owner while lease is still active.
        if current_owner == owner_id and lease_active:
            return {
                "card_id": snapshot.card_id,
                "issue_number": issue_number,
                "lease": snapshot.lease.model_dump(),
                "version": snapshot.version,
            }

        if current_owner and current_owner != owner_id and lease_active:
            return None

        new_epoch = int(snapshot.lease.epoch or 0) + 1
        new_lease = LeaseInfo(
            owner_id=owner_id,
            acquired_at=now.isoformat(),
            expires_at=(now + timedelta(seconds=max(1, int(lease_seconds)))).isoformat(),
            epoch=new_epoch,
        )
        new_snapshot = CardSnapshot(
            card_id=snapshot.card_id,
            state=snapshot.state,
            backend=snapshot.backend,
            version=int(snapshot.version) + 1,
            lease=new_lease,
            metadata=dict(snapshot.metadata or {}),
        )
        patch_headers: Dict[str, str] = {}
        if etag:
            patch_headers["If-Match"] = etag
        try:
            await self._request_json(
                "PATCH",
                f"/issues/{issue_number}",
                payload={"body": encode_snapshot(new_snapshot)},
                extra_headers=patch_headers or None,
            )
        except GiteaAdapterConflictError:
            return None

        return {
            "card_id": new_snapshot.card_id,
            "issue_number": issue_number,
            "lease": new_snapshot.lease.model_dump(),
            "version": new_snapshot.version,
        }

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
        comment = build_event_comment(
            event_type,
            payload,
            idempotency_key=idempotency_key,
        )
        await self._request_json(
            "POST",
            f"/issues/{issue_number}/comments",
            payload={"body": comment},
        )

    async def transition_state(
        self,
        card_id: str,
        *,
        from_state: str,
        to_state: str,
        reason: Optional[str] = None,
    ) -> None:
        self._validate_transition(from_state=from_state, to_state=to_state)
        issue_number = int(card_id)
        issue_response = await self._request_response_with_retry("GET", f"/issues/{issue_number}")
        issue = issue_response.json()
        if not isinstance(issue, dict):
            raise ValueError(f"Issue {issue_number} payload missing for transition.")
        snapshot = decode_snapshot(str(issue.get("body") or ""))
        if str(snapshot.state) != str(from_state):
            # Idempotent duplicate write: transition already applied.
            if str(snapshot.state) == str(to_state):
                return
            raise ValueError(
                f"Stale transition rejected for {card_id}: expected from_state={snapshot.state}, got {from_state}."
            )
        etag = issue_response.headers.get("ETag")
        new_snapshot = CardSnapshot(
            card_id=snapshot.card_id,
            state=str(to_state),
            backend=snapshot.backend,
            version=int(snapshot.version) + 1,
            lease=snapshot.lease,
            metadata=dict(snapshot.metadata or {}),
        )
        if reason:
            new_snapshot.metadata["transition_reason"] = reason
        patch_headers: Dict[str, str] = {}
        if etag:
            patch_headers["If-Match"] = etag
        try:
            await self._request_json(
                "PATCH",
                f"/issues/{issue_number}",
                payload={"body": encode_snapshot(new_snapshot)},
                extra_headers=patch_headers or None,
            )
        except GiteaAdapterConflictError as exc:
            raise ValueError(
                f"Stale transition rejected for {card_id}: compare-and-swap conflict."
            ) from exc

    async def release_or_fail(
        self,
        card_id: str,
        *,
        final_state: str,
        error: Optional[str] = None,
    ) -> None:
        issue_number = int(card_id)
        issue_response = await self._request_response_with_retry("GET", f"/issues/{issue_number}")
        issue = issue_response.json()
        if not isinstance(issue, dict):
            raise ValueError(f"Issue {issue_number} payload missing for release/fail.")
        snapshot = decode_snapshot(str(issue.get("body") or ""))
        target_state = str(final_state)

        # Idempotent duplicate write: already finalized and lease is released.
        if (
            str(snapshot.state) == target_state
            and not str(snapshot.lease.owner_id or "").strip()
            and not str(snapshot.lease.expires_at or "").strip()
        ):
            return

        self._validate_transition(from_state=str(snapshot.state), to_state=target_state)

        etag = issue_response.headers.get("ETag")
        released_lease = LeaseInfo(
            owner_id=None,
            acquired_at=None,
            expires_at=None,
            epoch=int(snapshot.lease.epoch or 0),
        )
        new_snapshot = CardSnapshot(
            card_id=snapshot.card_id,
            state=target_state,
            backend=snapshot.backend,
            version=int(snapshot.version) + 1,
            lease=released_lease,
            metadata=dict(snapshot.metadata or {}),
        )
        if error:
            new_snapshot.metadata["terminal_error"] = error
        patch_headers: Dict[str, str] = {}
        if etag:
            patch_headers["If-Match"] = etag
        try:
            await self._request_json(
                "PATCH",
                f"/issues/{issue_number}",
                payload={"body": encode_snapshot(new_snapshot)},
                extra_headers=patch_headers or None,
            )
        except GiteaAdapterConflictError as exc:
            raise ValueError(
                f"Stale release/fail rejected for {card_id}: compare-and-swap conflict."
            ) from exc

        event_payload = {"final_state": target_state}
        if error:
            event_payload["error"] = error
        event_payload["idempotency_key"] = f"release:{new_snapshot.version}:{target_state}"
        await self.append_event(
            str(issue_number),
            event_type="release_or_fail",
            payload=event_payload,
        )

    @staticmethod
    def _validate_transition(*, from_state: str, to_state: str) -> None:
        """
        Transition rules are derived from the canonical Orket state machine.
        """
        try:
            current = CardStatus(str(from_state))
            requested = CardStatus(str(to_state))
        except ValueError as exc:
            raise ValueError(f"Unknown card status transition: {from_state} -> {to_state}") from exc
        try:
            # Adapter precondition check only; persistence semantics come in later slices.
            wait_reason = None
            if requested in {CardStatus.BLOCKED, CardStatus.WAITING_FOR_DEVELOPER}:
                wait_reason = WaitReason.SYSTEM
            StateMachine.validate_transition(
                CardType.ISSUE,
                current,
                requested,
                roles=["system", "integrity_guard"],
                wait_reason=wait_reason,
            )
        except StateMachineError as exc:
            raise ValueError(f"Invalid state transition: {from_state} -> {to_state}") from exc

    @staticmethod
    def _parse_iso(raw: Optional[str]) -> Optional[datetime]:
        if not raw:
            return None
        try:
            return datetime.fromisoformat(str(raw))
        except ValueError:
            return None

    @staticmethod
    def _now_utc() -> datetime:
        return datetime.now(UTC)

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
            except Exception:
                continue
            if str(event.idempotency_key or "").strip() == idempotency_key:
                return True
        return False

    @staticmethod
    def _classify_http_error(*, status_code: Optional[int], exc: Exception) -> GiteaAdapterError:
        if status_code == 429:
            return GiteaAdapterRateLimitError(str(exc))
        if status_code in {401, 403}:
            return GiteaAdapterAuthError(str(exc))
        if status_code in {409, 412}:
            return GiteaAdapterConflictError(str(exc))
        return GiteaAdapterError(str(exc))

    def _log_failure(self, failure_class: str, **fields: Any) -> None:
        record = {
            "event": "gitea_state_adapter_failure",
            "backend": "gitea",
            "failure_class": failure_class,
            **fields,
        }
        logger.warning(json.dumps(record, ensure_ascii=False))
