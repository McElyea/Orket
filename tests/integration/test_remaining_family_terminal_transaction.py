"""Real SDK/legacy/review closeout cannot retain half a terminal transaction."""
from __future__ import annotations

import asyncio

import pytest

from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.core.contracts import AttemptRecord, FinalTruthRecord, RunRecord
from orket.core.domain import AttemptState, RunState
from orket.core.domain.control_plane_final_truth import validate_terminal_record_consistency
from tests.helpers.remaining_family_authority import database_for, records, run_family

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
FAULT = "remaining-family-terminal-write-interrupted"
BOUNDARIES = [
    (AsyncControlPlaneExecutionRepository, "save_attempt_record"),
    (AsyncControlPlaneExecutionRepository, "save_step_record"),
    (AsyncControlPlaneRecordRepository, "append_effect_journal_entry"),
    (AsyncControlPlaneRecordRepository, "save_final_truth"),
    (AsyncControlPlaneExecutionRepository, "save_run_record"),
]


def terminal_write(record):
    if isinstance(record, RunRecord):
        return record.lifecycle_state is RunState.COMPLETED
    if isinstance(record, AttemptRecord):
        return record.attempt_state is AttemptState.COMPLETED
    if isinstance(record, FinalTruthRecord):
        return record.result_class.value == "success"
    return getattr(record, "step_kind", "").endswith("closeout") or getattr(record, "step_id", "").endswith(":closeout")


@pytest.mark.parametrize("family", ["sdk", "legacy", "review"])
@pytest.mark.parametrize("repository_type,method", BOUNDARIES, ids=[method for _, method in BOUNDARIES])
@pytest.mark.parametrize("cancel", [False, True], ids=["failure", "cancelled"])
# Layer: integration
async def test_terminal_write_interruption_does_not_retain_partial_success(
    family, repository_type, method, cancel, tmp_path, monkeypatch,
):
    original = getattr(repository_type, method)
    interrupted = []

    async def write(repository, **kwargs):
        record = kwargs.get("record", kwargs.get("entry"))
        saved = await original(repository, **kwargs)
        if terminal_write(record) and not interrupted:
            interrupted.append(True)
            if cancel:
                raise asyncio.CancelledError(FAULT)
            raise RuntimeError(FAULT)
        return saved

    monkeypatch.setattr(repository_type, method, write)
    with pytest.raises(asyncio.CancelledError if cancel else RuntimeError, match=None if cancel else FAULT):
        await run_family(family, tmp_path)
    assert interrupted
    observed = await records(database_for(family, tmp_path))
    runs = [RunRecord.model_validate(row) for row in observed["control_plane_runs"]]
    assert len(runs) == 1
    attempts = [AttemptRecord.model_validate(row) for row in observed["control_plane_attempts"]]
    truths = [FinalTruthRecord.model_validate(row) for row in observed["final_truth_records"]]
    assert not any(truth.result_class.value == "success" for truth in truths)
    validate_terminal_record_consistency(runs[0], attempts[0], truths[0] if truths else None)
    if not truths:
        assert runs[0].lifecycle_state is RunState.EXECUTING
        assert attempts[0].attempt_state is AttemptState.EXECUTING and attempts[0].end_timestamp is None
        assert not any(row["step_kind"].endswith("closeout") for row in observed["control_plane_steps"])
        assert not any(row["step_id"].endswith(":closeout") for row in observed["effect_journal_entries"])


@pytest.mark.parametrize("family", ["sdk", "legacy", "review"])
# Layer: integration
async def test_healthy_terminal_records_agree_with_real_family_result(family, tmp_path):
    result = await run_family(family, tmp_path)
    rows = await records(database_for(family, tmp_path))
    run = RunRecord.model_validate(rows["control_plane_runs"][0])
    attempt = AttemptRecord.model_validate(rows["control_plane_attempts"][0])
    truth = FinalTruthRecord.model_validate(rows["final_truth_records"][0])
    assert validate_terminal_record_consistency(run, attempt, truth)
    assert truth.result_class.value == "success"
    if family == "review":
        assert result.ok and result.control_plane["run_state"] == "completed"
    else:
        assert result.control_plane["control_plane_final_truth_record_id"] == truth.final_truth_record_id
        if family == "sdk":
            from pathlib import Path
            assert await asyncio.to_thread((Path(result.artifact_root) / "result.txt").read_text) == "seed=321;mode=basic"


# Layer: integration
async def test_review_failure_closeout_preserves_the_originating_error(tmp_path, monkeypatch, caplog):
    original = AsyncControlPlaneExecutionRepository.save_run_record
    attempted = []

    async def write(repository, *, record):
        if record.lifecycle_state is RunState.COMPLETED:
            attempted.append("completed")
            raise RuntimeError(FAULT)
        if record.lifecycle_state is RunState.FAILED_TERMINAL:
            attempted.append("failure-closeout")
            raise OSError("secondary-closeout-failure")
        return await original(repository, record=record)

    monkeypatch.setattr(AsyncControlPlaneExecutionRepository, "save_run_record", write)
    with pytest.raises(RuntimeError, match=FAULT) as caught:
        await run_family("review", tmp_path)
    assert attempted == ["completed", "failure-closeout"]
    assert "also raised OSError" in caught.value.__notes__[0]
    assert "Review failure closeout also failed" in caplog.text
    rows = await records(database_for("review", tmp_path))
    assert not rows["final_truth_records"]
    assert rows["control_plane_runs"][0]["lifecycle_state"] == "executing"
    assert rows["control_plane_attempts"][0]["attempt_state"] == "attempt_executing"
