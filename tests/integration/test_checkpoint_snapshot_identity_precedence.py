from __future__ import annotations

import json
from pathlib import Path

import pytest

from orket.application.workflows.turn_checkpoint_snapshot import checkpoint_snapshot_integrity_ref
from tests.helpers.turn_control_plane_clock import deterministic_turn_clock as deterministic_turn_clock
from tests.integration.test_turn_executor_control_plane_evidence import (
    _attempt_id,
    _context,
    _executor,
    _issue,
    _Model,
    _observe_snapshot_namespace,
    _role,
    _run_id,
    _seed_checkpoint_only,
    _Toolbox,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio, pytest.mark.usefixtures("deterministic_turn_clock")]


# Layer: integration
@pytest.mark.parametrize("reentry", ["completed", "resume"])
async def test_snapshot_integrity_refusal_precedes_namespace_identity_validation(
    tmp_path: Path,
    reentry: str,
) -> None:
    if reentry == "completed":
        control_plane, executor = _executor(tmp_path)
        model, toolbox = _Model(), _Toolbox()
        seeded_result = await executor.execute_turn(_issue(), _role(), model, toolbox, _context())
    else:
        control_plane, executor, _run, _attempt, _checkpoint, _args = await _seed_checkpoint_only(tmp_path)
        model, toolbox = _Model(), _Toolbox()
        seeded_result = None
    checkpoint_before = await control_plane.publication.repository.get_checkpoint(
        checkpoint_id=f"turn-tool-checkpoint:{_attempt_id()}"
    )
    snapshot = await _observe_snapshot_namespace(tmp_path, "issue:OTHER")
    model_calls_before, tool_calls_before = model.calls, toolbox.calls

    result = await executor.execute_turn(
        _issue(), _role(), model, toolbox, _context(resume_mode=reentry == "resume")
    )
    checkpoint_after = await control_plane.publication.repository.get_checkpoint(
        checkpoint_id=f"turn-tool-checkpoint:{_attempt_id()}"
    )
    retained = await _observe_snapshot_namespace(tmp_path)
    run = await control_plane.execution_repository.get_run_record(run_id=_run_id())
    attempt = await control_plane.execution_repository.get_attempt_record(attempt_id=_attempt_id())

    assert result.success is False
    assert result.error is not None
    assert "E_CHECKPOINT_SNAPSHOT_INTEGRITY_MISMATCH" in result.error
    assert "snapshot namespace scope does not match current request" not in result.error
    assert model.calls == model_calls_before
    assert toolbox.calls == tool_calls_before
    assert checkpoint_before is not None
    assert checkpoint_after == checkpoint_before
    assert retained["after"] == snapshot["after"]
    assert checkpoint_before.integrity_verification_ref == checkpoint_snapshot_integrity_ref(
        json.loads(snapshot["before"])
    )
    assert checkpoint_before.integrity_verification_ref != checkpoint_snapshot_integrity_ref(snapshot["payload"])
    assert run is not None
    assert attempt is not None
    if reentry == "completed":
        assert seeded_result is not None
        assert seeded_result.success is True
    else:
        assert seeded_result is None
