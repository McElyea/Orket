"""Canonical card acceptance composition for an explicitly selected runtime store."""
from __future__ import annotations

from pathlib import Path

from orket.adapters.storage.card_acceptance_evidence_store import CardAcceptanceEvidenceStore
from orket.application.services.card_acceptance_service import CardAcceptanceService
from orket.application.services.card_completion_service import CardCompletionService


def build_card_completion_service(*, db_path: str | Path, workspace_root: Path) -> CardCompletionService:
    cards_path = Path(db_path)
    evidence_path = cards_path.with_name(cards_path.name + ".card_acceptance.sqlite3")
    return CardCompletionService(workspace_root=workspace_root, acceptance=CardAcceptanceService(
        CardAcceptanceEvidenceStore(evidence_path),
    ))
