"""Review support and note time through the real engine with a declared model fixture."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta, timezone

import pytest

from orket.adapters.llm.local_model_provider import ModelResponse
from orket.application.services.orchestrator_review_preflight_service import OrchestratorReviewPreflightService
from orket.core.cards_runtime_contract import DEFAULT_RUNTIME_VERIFICATION_INDEX_PATH
from orket.orchestration.engine import OrchestrationEngine
from orket.schema import CardStatus
from tests.helpers.protocol_ledger_clock import ProtocolLedgerClock
from tests.integration.test_governed_guard_epic_rejection import GovernedRejectingProvider
from tests.integration.test_system_acceptance_flow import _build_assets, _patch_provider

pytestmark = pytest.mark.integration


class ReviewFixtureProvider(GovernedRejectingProvider):
    def __init__(self, invalid_python):
        self.invalid_python = invalid_python

    async def complete(self, messages):
        response = await super().complete(messages)
        payload = json.loads(response.content)
        if self.invalid_python:
            for call in payload["tool_calls"]:
                if call["tool"] == "write_file" and call["args"]["path"] == "agent_output/main.py":
                    call["args"]["content"] = "def broken(:\n"
        return ModelResponse(content=json.dumps(payload), raw={"model": "dummy", "total_tokens": 1})


def _read_records(workspace):
    index = json.loads((workspace / DEFAULT_RUNTIME_VERIFICATION_INDEX_PATH).read_text(encoding="utf-8"))
    return [json.loads((workspace / item["record_path"]).read_text(encoding="utf-8"))
            for item in index["records"]]


@pytest.mark.parametrize("invalid_python", [False, True], ids=["successful-support", "failed-support"])
@pytest.mark.parametrize("offset", [timedelta(), timedelta(hours=5, minutes=30)], ids=["utc", "explicit-offset"])
async def test_review_publications_use_engine_selected_clock(tmp_path, monkeypatch, invalid_python, offset):
    await asyncio.to_thread(_build_assets, tmp_path, with_guard=True, epic_id="review_clock")
    _patch_provider(monkeypatch, ReviewFixtureProvider(invalid_python))
    monkeypatch.setenv("ORKET_PROTOCOL_GOVERNED_ENABLED", "true")
    clock = ProtocolLedgerClock()
    clock.current = clock.current.replace(year=2041, month=6, day=15, hour=12, tzinfo=timezone(offset))
    workspace = tmp_path / "workspace"
    async with OrchestrationEngine.open(
        workspace, department="core", db_path=str(tmp_path / "cards.db"),
        config_root=tmp_path, runtime_inputs=clock,
    ) as engine:
        outcome = await engine.run_card("review_clock")
        issue = await engine.cards.get_by_id("ISSUE-A")
        assert issue.status == CardStatus.BLOCKED
        assert not outcome.succeeded
        records = await asyncio.to_thread(_read_records, workspace)
        notes = engine._pipeline.orchestrator.notes.all()
    assert records, "actual runtime verifier support history is required"
    assert all(record["provenance"]["recorded_at"].startswith("2041-") for record in records)
    assert all(datetime.fromisoformat(record["provenance"]["recorded_at"]).utcoffset() == timedelta()
               for record in records)
    if invalid_python:
        assert notes, "actual failed-review notes are required"
        assert all(note.created_at.year == 2041 for note in notes)
        assert all(note.id == str(note.created_at.timestamp()) for note in notes)
        assert all(note.created_at.utcoffset() == timedelta() for note in notes)


@pytest.mark.parametrize("invalid", [datetime(2041, 6, 15, 12), "2041-06-15T12:00:00+00:00"], ids=["naive", "not-datetime"])
@pytest.mark.parametrize("boundary", ["support", "note"])
async def test_review_invalid_selected_time_refuses_publication(tmp_path, monkeypatch, invalid, boundary):
    await asyncio.to_thread(_build_assets, tmp_path, with_guard=True, epic_id="review_time_refusal")
    _patch_provider(monkeypatch, ReviewFixtureProvider(invalid_python=True))
    monkeypatch.setenv("ORKET_PROTOCOL_GOVERNED_ENABLED", "true")
    original = OrchestratorReviewPreflightService.run
    refusals = []

    async def select_clock(service, **kwargs):
        samples = 0

        def clock():
            nonlocal samples
            samples += 1
            return datetime(2041, 6, 15, 12, tzinfo=UTC) if boundary == "note" and samples == 1 else invalid

        service.utc_now = clock
        try:
            return await original(service, **kwargs)
        except ValueError as exc:
            refusals.append(str(exc))
            raise

    monkeypatch.setattr(OrchestratorReviewPreflightService, "run", select_clock)
    workspace = tmp_path / "workspace"
    async with OrchestrationEngine.open(
        workspace, department="core", db_path=str(tmp_path / "cards.db"), config_root=tmp_path,
    ) as engine:
        outcome = await engine.run_card("review_time_refusal")
        notes = engine._pipeline.orchestrator.notes.all()
        assert not outcome.succeeded
    assert refusals and all("E_REVIEW_PREFLIGHT_TIME_REQUIRES_AWARE_DATETIME" in value for value in refusals)
    assert not notes
    if boundary == "support":
        assert not await asyncio.to_thread((workspace / DEFAULT_RUNTIME_VERIFICATION_INDEX_PATH).exists)
    else:
        records = await asyncio.to_thread(_read_records, workspace)
        assert records and all(record["provenance"]["recorded_at"] == "2041-06-15T12:00:00+00:00" for record in records)
