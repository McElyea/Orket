"""Application-owned acceptance observations for card and run operator views."""
from __future__ import annotations

from typing import Any

from orket.application.services.card_completion_outcome_service import inspect_build_completion, project_card_completion
from orket.application.services.run_ledger_summary_projection import validated_run_ledger_record_projection
from orket.core.contracts.card_completion_commit import SUCCESSFUL_CARD_STATUSES
from orket.core.contracts.repositories import CardRepository
from orket.core.domain.records import IssueRecord

_RUNNING_CARD_STATUSES = {"in_progress", "started"}
_BLOCKED_CARD_STATUSES = {"blocked", "guard_rejected", "canceled", "archived"}
_REVIEW_CARD_STATUSES = {"code_review", "awaiting_guard_review", "guard_requested_changes"}
_TERMINAL_FAILURE_CATEGORIES = {"prebuild_blocked", "artifact_run_failed"}


def card_filter_bucket(*, raw_status: str, lifecycle_category: str, completion_accepted: bool) -> str:
    if completion_accepted:
        return "completed"
    if raw_status in SUCCESSFUL_CARD_STATUSES:
        return "review"
    if lifecycle_category in _TERMINAL_FAILURE_CATEGORIES:
        return "terminal_failure"
    if raw_status in _BLOCKED_CARD_STATUSES:
        return "blocked"
    if raw_status in _REVIEW_CARD_STATUSES:
        return "review"
    if raw_status in _RUNNING_CARD_STATUSES:
        return "running"
    return "open"


async def read_operator_card(*, cards: CardRepository, card_id: str) -> tuple[dict[str, Any], dict[str, Any]] | None:
    async with cards.completion_write_guard():
        record = await cards.get_by_id(card_id)
        if record is None:
            return None
        return record.model_dump(mode="json"), await project_card_completion(cards=cards, record=record)


async def read_operator_card_page(
    *, cards: CardRepository, **filters: Any,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    async with cards.completion_write_guard():
        rows = await cards.list_cards(**filters)
        return [(row, await project_card_completion(cards=cards, record=IssueRecord.model_validate(row))) for row in rows]


async def inspect_operator_run_completion(*, cards: CardRepository, run: dict[str, Any] | None) -> dict[str, Any]:
    result: dict[str, Any] = {"completion_accepted": False, "completion_rejection": None,
                              "accepted_receipts": {}, "unverified_cards": {}}
    published = (run or {}).get("artifact_json", {}).get("card_completion_outcome")
    build_id = (run or {}).get("build_id")
    if not isinstance(published, dict) or not isinstance(build_id, str) or not build_id:
        return {**result, "completion_rejection": "E_CARD_RUN_COMPLETION_OUTCOME_MISSING"}
    expected = published.get("expected_card_ids")
    if (published.get("build_id") != build_id or not isinstance(expected, list) or not expected
            or any(not isinstance(card_id, str) or not card_id for card_id in expected)
            or len(set(expected)) != len(expected)):
        return {**result, "completion_rejection": "E_CARD_RUN_COMPLETION_SCOPE_INVALID"}
    current = await inspect_build_completion(cards=cards, build_id=build_id, expected_card_ids=tuple(expected))
    result.update(accepted_receipts=dict(current.accepted_receipts), unverified_cards=dict(current.unverified_cards))
    if not current.sufficient:
        result["completion_rejection"] = current.failure_reason
    elif str((run or {}).get("status") or "").lower() not in {"done", "completed"}:
        result["completion_rejection"] = "E_CARD_RUN_NOT_COMPLETED"
    elif published.get("acceptance_satisfied") is not True or published != current.to_artifact():
        result["completion_rejection"] = "E_CARD_RUN_COMPLETION_OUTCOME_STALE"
    else:
        result["completion_accepted"] = True
    return result


async def load_operator_run_projection(*, engine: Any, session_id: str) -> dict[str, Any] | None:
    run_record = await engine.run_ledger.get_run(session_id)
    session = await engine.sessions.get_session(session_id)
    if run_record is None and session is None:
        return None
    run = validated_run_ledger_record_projection(run_record)
    status = (run or {}).get("status")
    if status is None and isinstance(session, dict):
        status = session.get("status")
    backlog = await engine.cards.get_by_session(session_id)
    return {"session_id": session_id, "status": status, "summary": dict((run or {}).get("summary_json") or {}),
            "artifacts": dict((run or {}).get("artifact_json") or {}), "issue_count": len(backlog),
            "completion": await inspect_operator_run_completion(cards=engine.cards, run=run)}


def operator_verification(completion: dict[str, Any]) -> dict[str, Any]:
    if completion["completion_accepted"]:
        return {"status": "verified", "summary": "Retained evidence satisfies the declared card acceptance criteria.",
                "reason_codes": ["verification.card_completion_accepted"]}
    return {"status": "unverified", "summary": "Declared card completion acceptance is unverified.",
            "reason_codes": ["verification.card_completion_unverified", completion["completion_rejection"]]}
