from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any, Protocol

from orket.logging import log_event

DEFAULT_STATE_RECONCILIATION_POLICY = "halt_and_alert"


class SQLiteCardReader(Protocol):
    async def get_by_id(self, card_id: str) -> Any | None: ...


class GiteaCardSnapshotReader(Protocol):
    async def fetch_card_snapshot(self, card_id: str) -> dict[str, Any] | None: ...


class StateReconciliationService:
    def __init__(
        self,
        *,
        sqlite_cards: SQLiteCardReader,
        gitea_cards: GiteaCardSnapshotReader,
        authority_policy: str = DEFAULT_STATE_RECONCILIATION_POLICY,
        workspace: Path | None = None,
    ) -> None:
        self.sqlite_cards = sqlite_cards
        self.gitea_cards = gitea_cards
        self.authority_policy = str(authority_policy or DEFAULT_STATE_RECONCILIATION_POLICY).strip()
        self.workspace = workspace

    async def reconcile(self, card_ids: Iterable[str]) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        conflicts: list[dict[str, Any]] = []
        for card_id in _normalize_card_ids(card_ids):
            row = await self._reconcile_one(card_id)
            rows.append(row)
            if row["result"] == "conflict":
                conflicts.append(row)
                log_event(
                    "state_reconciliation_conflict",
                    row,
                    workspace=self.workspace,
                )
        return {
            "ok": not conflicts,
            "authority_policy": self.authority_policy,
            "checked_count": len(rows),
            "conflict_count": len(conflicts),
            "rows": rows,
            "conflicts": conflicts,
        }

    async def _reconcile_one(self, card_id: str) -> dict[str, Any]:
        sqlite_record = await self.sqlite_cards.get_by_id(card_id)
        gitea_snapshot = await self.gitea_cards.fetch_card_snapshot(card_id)
        sqlite_state = _record_state(sqlite_record)
        gitea_state = _snapshot_state(gitea_snapshot)
        result = "success" if sqlite_state is not None and sqlite_state == gitea_state else "conflict"
        conflict_type = _conflict_type(sqlite_state=sqlite_state, gitea_state=gitea_state)
        row = {
            "card_id": card_id,
            "sqlite_state": sqlite_state,
            "gitea_state": gitea_state,
            "gitea_version": _snapshot_version(gitea_snapshot),
            "authority_policy": self.authority_policy,
            "result": result,
        }
        if conflict_type:
            row["conflict_type"] = conflict_type
        return row


def _normalize_card_ids(card_ids: Iterable[str]) -> list[str]:
    return sorted({str(card_id).strip() for card_id in card_ids if str(card_id).strip()})


def _record_state(record: Any | None) -> str | None:
    if record is None:
        return None
    raw_status = getattr(record, "status", None)
    value = getattr(raw_status, "value", raw_status)
    token = str(value or "").strip().lower()
    return token or None


def _snapshot_state(snapshot: dict[str, Any] | None) -> str | None:
    if not isinstance(snapshot, dict):
        return None
    token = str(snapshot.get("state") or "").strip().lower()
    return token or None


def _snapshot_version(snapshot: dict[str, Any] | None) -> int | None:
    if not isinstance(snapshot, dict):
        return None
    try:
        return int(snapshot.get("version"))
    except (TypeError, ValueError):
        return None


def _conflict_type(*, sqlite_state: str | None, gitea_state: str | None) -> str:
    if sqlite_state is None and gitea_state is None:
        return "missing_both"
    if sqlite_state is None:
        return "missing_sqlite"
    if gitea_state is None:
        return "missing_gitea"
    if sqlite_state != gitea_state:
        return "state_mismatch"
    return ""
