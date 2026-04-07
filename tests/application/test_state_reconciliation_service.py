# Layer: unit

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from orket.application.services.state_reconciliation_service import StateReconciliationService
from orket.schema import CardStatus


@dataclass
class _SQLiteCards:
    records: dict[str, Any]

    async def get_by_id(self, card_id: str) -> Any | None:
        return self.records.get(card_id)


@dataclass
class _GiteaCards:
    snapshots: dict[str, dict[str, Any]]

    async def fetch_card_snapshot(self, card_id: str) -> dict[str, Any] | None:
        return self.snapshots.get(card_id)


async def test_state_reconciliation_service_reports_success_when_states_match() -> None:
    service = StateReconciliationService(
        sqlite_cards=_SQLiteCards({"ISSUE-1": SimpleNamespace(status=CardStatus.READY)}),
        gitea_cards=_GiteaCards({"ISSUE-1": {"state": "ready", "version": 3}}),
    )

    result = await service.reconcile(["ISSUE-1"])

    assert result["ok"] is True
    assert result["conflicts"] == []
    assert result["rows"][0]["result"] == "success"


async def test_state_reconciliation_service_logs_conflicts_without_resolving(monkeypatch) -> None:
    events = []
    service = StateReconciliationService(
        sqlite_cards=_SQLiteCards({"ISSUE-1": SimpleNamespace(status=CardStatus.READY)}),
        gitea_cards=_GiteaCards({"ISSUE-1": {"state": "blocked", "version": 4}}),
    )

    monkeypatch.setattr(
        "orket.application.services.state_reconciliation_service.log_event",
        lambda event, data, workspace=None: events.append((event, data, workspace)),
    )

    result = await service.reconcile(["ISSUE-1"])

    assert result["ok"] is False
    assert result["conflicts"][0]["conflict_type"] == "state_mismatch"
    assert result["conflicts"][0]["authority_policy"] == "halt_and_alert"
    assert events[0][0] == "state_reconciliation_conflict"
