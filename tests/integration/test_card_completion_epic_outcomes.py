"""Session success requires a nonempty build with retained declared acceptance."""
from __future__ import annotations

import asyncio
import json

import aiosqlite
import pytest

from orket.adapters.storage.card_migrations import CARD_BOOTSTRAP_MIGRATIONS
from orket.adapters.storage.sqlite_migrations import SQLiteMigrationRunner
from orket.application.services.card_completion_outcome_service import inspect_build_completion
from orket.core.domain.records import IssueRecord
from orket.runtime.execution.execution_pipeline import ExecutionPipeline
from orket.schema import CardStatus
from tests.application.test_execution_pipeline_cards_epic_control_plane import _write_epic_assets
from tests.helpers.card_completion import complete_existing_card, completion_components

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["accepted", "guard_approved", "archived", "canceled", "forged_event", "missing_evidence", "missing_card", "empty"])
# Layer: integration
async def test_final_epic_outcome_requires_verified_cards(test_root, workspace, db_path, monkeypatch, caplog, case):
    await asyncio.to_thread(_write_epic_assets, test_root, "completion_epic")
    team_path = test_root / "model/core/teams/standard.json"
    team = json.loads(await asyncio.to_thread(team_path.read_text, encoding="utf-8"))
    team["seats"]["code_reviewer"] = {"name": "Reviewer", "roles": ["code_reviewer"]}
    await asyncio.to_thread(team_path.write_text, json.dumps(team), encoding="utf-8")
    if case == "missing_card":
        epic_path = test_root / "model/core/epics/completion_epic.json"
        epic = json.loads(await asyncio.to_thread(epic_path.read_text, encoding="utf-8"))
        epic["issues"].append({**epic["issues"][0], "id": "ISSUE-2"})
        await asyncio.to_thread(epic_path.write_text, json.dumps(epic), encoding="utf-8")
    async with ExecutionPipeline.open(workspace, department="core", db_path=db_path, config_root=test_root) as pipeline:
        execute_epic = pipeline.orchestrator.execute_epic

        async def execute_fixture(**kwargs):
            if case in {"accepted", "guard_approved", "missing_evidence", "missing_card"}:
                service = pipeline.runtime_context.card_completion
                target = CardStatus.GUARD_APPROVED if case == "guard_approved" else CardStatus.DONE
                await complete_existing_card(pipeline.async_cards, "ISSUE-1", workspace, service=service, target_status=target)
                if case == "missing_evidence":
                    await asyncio.to_thread(service.acceptance.evidence_store.db_path.unlink)
            if case in {"empty", "missing_card"}:
                record = await pipeline.async_cards.get_by_id("ISSUE-2" if case == "missing_card" else "ISSUE-1")
                record.build_id = "other-build"
                await pipeline.async_cards.save(record)
            elif case in {"archived", "canceled", "forged_event"}:
                await pipeline.async_cards.update_status("ISSUE-1", CardStatus.CANCELED if case == "forged_event" else CardStatus(case))
            if case == "forged_event":
                monkeypatch.setattr(pipeline.orchestrator.loop_policy_node, "no_candidate_outcome",
                                    lambda backlog: {"is_done": True, "event_name": "orchestrator_epic_complete"})
            await execute_epic(**kwargs)

        monkeypatch.setattr(pipeline.orchestrator, "execute_epic", execute_fixture)
        try:
            result = await pipeline.run_epic("completion_epic", build_id="build", session_id="completion-session")
            ledger = await pipeline.run_ledger.get_run("completion-session")
            outcome = ledger["artifact_json"]["card_completion_outcome"]
            accepted = case in {"accepted", "guard_approved"}
            expected = "done" if accepted else "incomplete" if case == "empty" else "terminal_failure"
            assert result.succeeded is accepted
            assert result.observation == "published" and result.publication_ref in result.evidence_refs
            assert result.run.model_dump(mode="json") == ledger["artifact_json"]["control_plane_run_record"]
            assert ledger["status"] == expected
            assert outcome["acceptance_satisfied"] is accepted
            events = [record.message for record in caplog.records if record.name == "orket"]
            assert "orchestrator_epic_stopped" in events
            assert ("orchestrator_epic_complete" in events) is accepted
            run = ledger["artifact_json"]["control_plane_run_record"]
            truth = await pipeline.orchestrator.control_plane_repository.get_final_truth(run_id=run["run_id"])
            assert result.final_truth == truth
            if accepted:
                receipt = await pipeline.async_cards.read_completion_receipt("ISSUE-1")
                assert outcome["accepted_receipts"] == {"ISSUE-1": receipt.digest}
                assert truth.result_class.value == "success"
            elif case == "empty":
                assert outcome["diagnostics"] == ["empty_backlog"] and truth is None
            else:
                assert ("ISSUE-2" if case == "missing_card" else "ISSUE-1") in outcome["unverified_cards"]
                assert truth.result_class.value != "success"
        finally:
            await pipeline.close()


@pytest.mark.asyncio
# Layer: integration
async def test_migrated_terminal_card_is_not_verified_build_success(tmp_path):
    db = tmp_path / "legacy.db"
    async with aiosqlite.connect(db) as connection:
        await SQLiteMigrationRunner(namespace="card_repository").apply(connection, CARD_BOOTSTRAP_MIGRATIONS)
        await connection.execute("INSERT INTO issues (id, summary, seat, type, priority, status, build_id) "
                                 "VALUES ('legacy', 'Old work', 'developer', 'issue', 2.0, 'done', 'build')")
        await connection.execute("PRAGMA user_version=1")
        await connection.commit()
    repo, _ = completion_components(db, tmp_path / "workspace")
    outcome = await inspect_build_completion(cards=repo, build_id="build", expected_card_ids=("legacy",))
    assert not outcome.sufficient
    assert outcome.to_artifact()["unverified_cards"] == {"legacy": "E_CARD_COMPLETION_RECEIPT_MISSING"}
    assert (await repo.get_by_id("legacy")).status == CardStatus.DONE


@pytest.mark.asyncio
# Layer: integration
async def test_complete_build_inspection_holds_guard_across_inventory_and_receipts(tmp_path):
    repo, service = completion_components(tmp_path / "cards.db", tmp_path / "workspace")
    await repo.save(IssueRecord(id="card", summary="Increment", seat="developer", build_id="build"))
    await complete_existing_card(repo, "card", service.workspace_root, service=service)
    observing = asyncio.Event()
    release = asyncio.Event()
    original = service.inspect_completion_receipt

    async def paused_inspection(**kwargs):
        result = await original(**kwargs)
        observing.set()
        await release.wait()
        return result

    service.inspect_completion_receipt = paused_inspection
    snapshot = asyncio.create_task(inspect_build_completion(cards=repo, build_id="build", expected_card_ids=("card",)))
    await asyncio.wait_for(observing.wait(), timeout=5)
    other, _ = completion_components(repo.db_path, service.workspace_root)
    inserting = asyncio.create_task(other.save(IssueRecord(id="new", summary="More work", seat="developer", build_id="build")))
    try:
        finished, _ = await asyncio.wait({inserting}, timeout=0.1)
        assert not finished
    finally:
        release.set()
        outcome, _ = await asyncio.gather(snapshot, inserting)
    assert outcome.sufficient and len(outcome.backlog) == 1
    assert not (await inspect_build_completion(cards=repo, build_id="build", expected_card_ids=("card",))).sufficient
