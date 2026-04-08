from __future__ import annotations

import os
from datetime import timedelta
from typing import Any

from pydantic import ValidationError

from .gitea_state_errors import GiteaAdapterConflictError
from .gitea_state_models import CardSnapshot, LeaseInfo, decode_snapshot, encode_snapshot


class GiteaLeaseManager:
    """Lease acquisition and renewal operations for Gitea-backed cards."""

    def __init__(self, adapter: Any) -> None:
        self.adapter = adapter

    @staticmethod
    def _max_issue_body_bytes() -> int:
        raw = str(os.getenv("ORKET_GITEA_ISSUE_BODY_MAX_BYTES", "65000")).strip()
        try:
            return max(1, int(raw))
        except ValueError:
            return 65000

    @classmethod
    def _encode_snapshot_body(cls, snapshot: CardSnapshot) -> str:
        body = encode_snapshot(snapshot)
        if len(body.encode("utf-8")) > cls._max_issue_body_bytes():
            raise ValueError("E_GITEA_SNAPSHOT_BODY_TOO_LARGE")
        return body

    async def acquire_lease(
        self,
        card_id: str,
        *,
        owner_id: str,
        lease_seconds: int,
    ) -> dict[str, Any] | None:
        try:
            issue_number = int(card_id)
        except ValueError:
            self.adapter._log_failure(
                "invalid_card_id",
                operation="acquire_lease",
                card_id=str(card_id),
                error="non-numeric card id",
            )
            return None
        issue_response = await self.adapter._request_response_with_retry("GET", f"/issues/{issue_number}")
        issue = issue_response.json()
        if not isinstance(issue, dict):
            return None

        try:
            snapshot = decode_snapshot(str(issue.get("body") or ""))
        except (ValueError, ValidationError):
            return None
        etag = issue_response.headers.get("ETag")
        now = self.adapter._now_utc()
        current_owner = str(snapshot.lease.owner_id or "").strip()
        expires_at = self.adapter._parse_iso(snapshot.lease.expires_at)
        lease_active = expires_at is not None and expires_at > now

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
        patch_headers: dict[str, str] = {}
        if etag:
            patch_headers["If-Match"] = etag
        try:
            body = self._encode_snapshot_body(new_snapshot)
        except ValueError:
            self.adapter._log_failure(
                "snapshot_body_too_large",
                operation="acquire_lease",
                card_id=str(card_id),
                error="E_GITEA_SNAPSHOT_BODY_TOO_LARGE",
            )
            raise
        try:
            await self.adapter._request_json(
                "PATCH",
                f"/issues/{issue_number}",
                payload={"body": body},
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

    async def renew_lease(
        self,
        card_id: str,
        *,
        owner_id: str,
        lease_seconds: int,
    ) -> dict[str, Any] | None:
        try:
            issue_number = int(card_id)
        except ValueError:
            log_failure = getattr(self.adapter, "_log_failure", None)
            if callable(log_failure):
                log_failure(
                    "invalid_card_id",
                    operation="renew_lease",
                    card_id=str(card_id),
                    error="non-numeric card id",
                )
            return None
        issue_response = await self.adapter._request_response_with_retry("GET", f"/issues/{issue_number}")
        issue = issue_response.json()
        if not isinstance(issue, dict):
            return None
        try:
            snapshot = decode_snapshot(str(issue.get("body") or ""))
        except (ValueError, ValidationError):
            return None
        if str(snapshot.lease.owner_id or "").strip() != owner_id:
            return None

        etag = issue_response.headers.get("ETag")
        now = self.adapter._now_utc()
        renewed_lease = LeaseInfo(
            owner_id=owner_id,
            acquired_at=str(snapshot.lease.acquired_at or now.isoformat()),
            expires_at=(now + timedelta(seconds=max(1, int(lease_seconds)))).isoformat(),
            epoch=int(snapshot.lease.epoch or 0),
        )
        new_snapshot = CardSnapshot(
            card_id=snapshot.card_id,
            state=snapshot.state,
            backend=snapshot.backend,
            version=int(snapshot.version) + 1,
            lease=renewed_lease,
            metadata=dict(snapshot.metadata or {}),
        )
        patch_headers: dict[str, str] = {}
        if etag:
            patch_headers["If-Match"] = etag
        try:
            body = self._encode_snapshot_body(new_snapshot)
        except ValueError:
            log_failure = getattr(self.adapter, "_log_failure", None)
            if callable(log_failure):
                log_failure(
                    "snapshot_body_too_large",
                    operation="renew_lease",
                    card_id=str(card_id),
                    error="E_GITEA_SNAPSHOT_BODY_TOO_LARGE",
                )
            raise
        try:
            await self.adapter._request_json(
                "PATCH",
                f"/issues/{issue_number}",
                payload={"body": body},
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
