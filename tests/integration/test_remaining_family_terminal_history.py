"""Retained family terminal consumers must refuse contradictory evidence without repair."""
from __future__ import annotations

import asyncio
import json

import aiosqlite
import pytest

from orket.application.services.extension_workload_control_plane_service import (
    ExtensionWorkloadControlPlaneService,
    build_extension_workload_control_plane_service,
)
from orket.application.services.review_run_control_plane_service import (
    ReviewRunControlPlaneService,
    build_review_run_control_plane_service,
)
from orket.core.domain import AuthoritySourceClass, ResultClass
from tests.helpers.remaining_family_authority import (
    database_for,
    records,
    repeat_closeout,
    retained_request,
    run_family,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
CASES = {
    "run-reference": ("control_plane_runs", "final_truth_record_id", "unbound"),
    "attempt-run": ("control_plane_attempts", "run_id", "different-run"),
    "truth-result-ref": ("final_truth_records", "authoritative_result_ref", "unbound"),
    "truth-authority": ("final_truth_records", "authority_sources", ["operator_attestation"]),
    "truth-missing": ("final_truth_records", "__delete__", None),
    "step-missing": ("control_plane_steps", "__delete__", None),
    "effect-missing": ("effect_journal_entries", "__delete__", None),
    "attempt-unfinished": ("control_plane_attempts", "__unfinished__", None),
    "step-attempt": ("control_plane_steps", "attempt_id", "different-attempt"),
    "step-input": ("control_plane_steps", "input_ref", "unbound"),
    "step-result": ("control_plane_steps", "output_ref", "unbound"),
    "effect-run": ("effect_journal_entries", "run_id", "different-run"),
    "effect-step": ("effect_journal_entries", "step_id", "different-step"),
    "effect-result": ("effect_journal_entries", "observed_result_ref", "unbound"),
}


class StopBeforeCloseout(BaseException):
    """Test boundary that suspends before closeout without starting failure compensation."""


async def damage(db, case):
    table, field, value = CASES[case]
    async with aiosqlite.connect(db) as connection:
        cursor = await connection.execute("SELECT rowid,payload_json FROM " + table)
        rows = [(rowid, json.loads(raw)) for rowid, raw in await cursor.fetchall()]
        for rowid, row in rows:
            if table in {"control_plane_steps", "effect_journal_entries"} and not row["step_id"].endswith(":closeout"):
                continue
            if field == "__delete__":
                await connection.execute("DELETE FROM " + table + " WHERE rowid=?", (rowid,))
                continue
            if field == "__unfinished__":
                row.update(attempt_state="attempt_executing", end_timestamp=None)
            else:
                row[field] = value
            await connection.execute("UPDATE " + table + " SET payload_json=? WHERE rowid=?", (json.dumps(row), rowid))
        await connection.commit()


@pytest.mark.parametrize("family", ["sdk", "legacy", "review"])
@pytest.mark.parametrize("case", ["coherent", *CASES])
# Layer: integration
async def test_retained_terminal_closeout_refuses_corruption_without_mutation(family, case, tmp_path):
    await run_family(family, tmp_path)
    owner, request = await retained_request(family, tmp_path)
    db = database_for(family, tmp_path)
    if case != "coherent":
        await damage(db, case)
    before = await records(db)
    if case == "coherent":
        assert await repeat_closeout(family, owner, request)
        if family == "review":
            assert (await owner.read_execution_summary(**request))["run_state"] == "completed"
    else:
        with pytest.raises(ValueError):
            await repeat_closeout(family, owner, request)
        if family == "review":
            with pytest.raises(ValueError):
                await owner.read_execution_summary(**request)
    assert await records(db) == before


@pytest.mark.parametrize("family", ["sdk", "legacy", "review"])
# Layer: integration
async def test_competing_completed_closeouts_preserve_one_retained_result(family, tmp_path):
    await run_family(family, tmp_path)
    owner, request = await retained_request(family, tmp_path)
    second, _ = await retained_request(family, tmp_path)
    db = database_for(family, tmp_path)
    before = await records(db)
    result = await asyncio.gather(repeat_closeout(family, owner, request), repeat_closeout(family, second, request))
    assert result[0] == result[1]
    assert await records(db) == before


@pytest.mark.parametrize("family", ["sdk", "legacy", "review"])
# Layer: integration
async def test_retained_success_cannot_be_reinterpreted_as_failure(family, tmp_path):
    await run_family(family, tmp_path)
    owner, request = await retained_request(family, tmp_path)
    db = database_for(family, tmp_path)
    before = await records(db)
    with pytest.raises(ValueError, match="CONFLICT"):
        if family == "review":
            await owner.finalize_failed(run_id=request["run_id"], failure_class="new-failure")
        else:
            await owner.finalize_execution(**(request | {"outcome": ResultClass.FAILED,
                "authoritative_result_ref": "changed-result", "authority_sources": [AuthoritySourceClass.RECEIPT_EVIDENCE]}))
    assert await records(db) == before


@pytest.mark.parametrize("family", ["sdk", "legacy", "review"])
@pytest.mark.parametrize("conflicting", [False, True], ids=["identical", "conflicting-outcomes"])
# Layer: integration
async def test_competing_initial_closeouts_publish_one_consistent_result(family, conflicting, tmp_path, monkeypatch):
    captured = []

    async def pause(owner, **kwargs):
        captured.append(kwargs)
        raise StopBeforeCloseout()

    service_type = ReviewRunControlPlaneService if family == "review" else ExtensionWorkloadControlPlaneService
    method = "finalize_completed" if family == "review" else "finalize_execution"
    with monkeypatch.context() as control:
        control.setattr(service_type, method, pause)
        with pytest.raises(StopBeforeCloseout):
            await run_family(family, tmp_path)
    assert len(captured) == 1
    db = database_for(family, tmp_path)
    assert not (await records(db))["final_truth_records"]
    if family == "review":
        first, second = [build_review_run_control_plane_service(db) for _ in range(2)]
        other = second.finalize_failed(**captured[0], failure_class="contending-failure") if conflicting else (
            second.finalize_completed(**captured[0]))
        calls = [first.finalize_completed(**captured[0]), other]
    else:
        first, second = [build_extension_workload_control_plane_service(project_root=tmp_path) for _ in range(2)]
        alternate = captured[0] | ({"outcome": ResultClass.FAILED, "failure_class": "contending-failure"}
                                   if conflicting else {})
        calls = [first.finalize_execution(**captured[0]), second.finalize_execution(**alternate)]
    results = await asyncio.gather(*calls, return_exceptions=True)
    errors = [r for r in results if isinstance(r, BaseException)]
    assert len(errors) == int(conflicting)
    if errors:
        assert isinstance(errors[0], ValueError) and "CONFLICT" in str(errors[0])
    else:
        assert results[0] == results[1]
    rows = await records(db)
    assert len(rows["final_truth_records"]) == 1
    result_class = rows["final_truth_records"][0]["result_class"]
    assert rows["control_plane_runs"][0]["lifecycle_state"] == ("completed" if result_class == "success" else "failed_terminal")
    assert rows["control_plane_attempts"][0]["attempt_state"] == ("attempt_completed" if result_class == "success" else "attempt_failed")
