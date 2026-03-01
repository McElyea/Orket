from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, Optional

from pydantic import ValidationError

from .gitea_state_models import CardSnapshot, LeaseInfo, decode_snapshot, encode_snapshot
from .gitea_state_errors import GiteaAdapterConflictError


class GiteaLeaseManager:
    """Lease acquisition and renewal operations for Gitea-backed cards."""

    def __init__(self, adapter: Any) -> None:
        self.adapter = adapter

    async def acquire_lease(
        self,
        card_id: str,
        *,
        owner_id: str,
        lease_seconds: int,
    ) -> Optional[Dict[str, Any]]:
        issue_number = int(card_id)
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
    ) -> Optional[Dict[str, Any]]:
        issue_number = int(card_id)
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
        except GiteaAdapterConflictError:
            return None

        return {
            "card_id": new_snapshot.card_id,
            "issue_number": issue_number,
            "lease": new_snapshot.lease.model_dump(),
            "version": new_snapshot.version,
        }
