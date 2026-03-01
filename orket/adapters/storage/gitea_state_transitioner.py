from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Dict, Optional

from pydantic import ValidationError

from orket.core.domain.state_machine import StateMachine, StateMachineError
from orket.schema import CardStatus, CardType, WaitReason

from .gitea_state_errors import GiteaAdapterConflictError
from .gitea_state_models import CardSnapshot, LeaseInfo, decode_snapshot, encode_snapshot


class GiteaStateTransitioner:
    """State transition and finalization operations for Gitea cards."""

    def __init__(self, adapter: Any) -> None:
        self.adapter = adapter

    async def transition_state(
        self,
        card_id: str,
        *,
        from_state: str,
        to_state: str,
        reason: Optional[str] = None,
    ) -> None:
        self.validate_transition(from_state=from_state, to_state=to_state)
        issue_number = int(card_id)
        issue_response = await self.adapter._request_response_with_retry("GET", f"/issues/{issue_number}")
        issue = issue_response.json()
        if not isinstance(issue, dict):
            raise ValueError(f"Issue {issue_number} payload missing for transition.")
        snapshot = decode_snapshot(str(issue.get("body") or ""))
        if str(snapshot.state) != str(from_state):
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
            await self.adapter._request_json(
                "PATCH",
                f"/issues/{issue_number}",
                payload={"body": encode_snapshot(new_snapshot)},
                extra_headers=patch_headers or None,
            )
        except GiteaAdapterConflictError as exc:
            raise ValueError(f"Stale transition rejected for {card_id}: compare-and-swap conflict.") from exc

    async def release_or_fail(
        self,
        card_id: str,
        *,
        final_state: str,
        error: Optional[str] = None,
    ) -> None:
        issue_number = int(card_id)
        issue_response = await self.adapter._request_response_with_retry("GET", f"/issues/{issue_number}")
        issue = issue_response.json()
        if not isinstance(issue, dict):
            raise ValueError(f"Issue {issue_number} payload missing for release/fail.")
        snapshot = decode_snapshot(str(issue.get("body") or ""))
        target_state = str(final_state)

        if (
            str(snapshot.state) == target_state
            and not str(snapshot.lease.owner_id or "").strip()
            and not str(snapshot.lease.expires_at or "").strip()
        ):
            return

        self.validate_transition(from_state=str(snapshot.state), to_state=target_state)

        etag = issue_response.headers.get("ETag")
        released_lease = LeaseInfo(owner_id=None, acquired_at=None, expires_at=None, epoch=int(snapshot.lease.epoch or 0))
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
            await self.adapter._request_json(
                "PATCH",
                f"/issues/{issue_number}",
                payload={"body": encode_snapshot(new_snapshot)},
                extra_headers=patch_headers or None,
            )
        except GiteaAdapterConflictError as exc:
            raise ValueError(f"Stale release/fail rejected for {card_id}: compare-and-swap conflict.") from exc

        event_payload = {"final_state": target_state, "idempotency_key": f"release:{new_snapshot.version}:{target_state}"}
        if error:
            event_payload["error"] = error
        await self.adapter.append_event(str(issue_number), event_type="release_or_fail", payload=event_payload)

    @staticmethod
    def validate_transition(*, from_state: str, to_state: str) -> None:
        try:
            current = CardStatus(str(from_state))
            requested = CardStatus(str(to_state))
        except ValueError as exc:
            raise ValueError(f"Unknown card status transition: {from_state} -> {to_state}") from exc
        try:
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
    def parse_iso(raw: Optional[str]) -> Optional[datetime]:
        if not raw:
            return None
        try:
            return datetime.fromisoformat(str(raw))
        except ValueError:
            return None

    @staticmethod
    def now_utc() -> datetime:
        return datetime.now(UTC)
