from __future__ import annotations

from datetime import UTC, datetime, timedelta
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
from orket.schema import CardStatus, CardType


class GiteaStateAdapter(StateBackendContract):
    """
    Experimental state backend adapter for Gitea issues.

    P1 slices:
    - Implemented: fetch_ready_cards, append_event, acquire_lease (CAS + lease epoch)
    - Pending: transitions persistence, release/fail semantics
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
    ):
        self.base_url = base_url.rstrip("/")
        self.owner = owner
        self.repo = repo
        self.ready_label = ready_label
        self.timeout_seconds = timeout_seconds
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

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        response = await self._request_response(
            method,
            path,
            params=params,
            payload=payload,
            extra_headers=extra_headers,
        )
        if not response.text.strip():
            return None
        return response.json()

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
        issue_response = await self._request_response("GET", f"/issues/{issue_number}")
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
        except httpx.HTTPStatusError as exc:
            if exc.response is not None and exc.response.status_code in {409, 412}:
                return None
            raise

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
        raise NotImplementedError("transition_state persistence is planned in next gitea adapter slice.")

    async def release_or_fail(
        self,
        card_id: str,
        *,
        final_state: str,
        error: Optional[str] = None,
    ) -> None:
        raise NotImplementedError("release_or_fail is planned in next gitea adapter slice.")

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
            StateMachine.validate_transition(
                CardType.ISSUE,
                current,
                requested,
                roles=["system", "integrity_guard"],
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
