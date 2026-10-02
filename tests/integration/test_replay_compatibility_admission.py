"""Native workspace compatibility checks; this does not replay tool effects."""
from copy import deepcopy

import pytest

from orket.adapters.execution.owned_io import run_owned_thread
from orket.runtime.evidence.replay_compatibility import (
    evaluate_replay_compatibility,
    resolve_ledger_schema_version,
)
from orket.runtime.evidence.workspace_snapshot import capture_workspace_state_snapshot

pytestmark = pytest.mark.asyncio


def _inputs(artifacts, *, enforce=True, complete=False):
    return dict(events=[{"kind": "run_started", "artifacts": artifacts}, {"kind": "run_finalized"}],
                current_contract_snapshots={}, current_policy_versions={}, current_runtime_contract_hash="",
                enforce_runtime_contract_compatibility=enforce, require_replay_artifact_completeness=complete)


@pytest.mark.integration
@pytest.mark.parametrize("count,missing", [(0.0, False), ("0", False), ("bad", True), (" ", True), ([], True)])
async def test_workspace_count_admission_does_not_repair_missing_contracts(tmp_path, count, missing):
    snapshot = await run_owned_thread(lambda: capture_workspace_state_snapshot(workspace=tmp_path), label="test-snapshot")
    snapshot["file_count"] = count
    inputs = _inputs({"run_determinism_class": "workspace", "workspace_state_snapshot": snapshot})
    before = deepcopy(inputs)
    report = await run_owned_thread(lambda: evaluate_replay_compatibility(**inputs), label="test-compatibility")
    assert report["path"] == "degraded" and report["status"] == "ok"
    assert ("workspace_state_snapshot.file_count" in report["missing_contract_fields"]) is missing
    assert report["mismatch_fields"] == [] and inputs == before


@pytest.mark.integration
async def test_native_workspace_changes_report_all_observed_mismatches(tmp_path):
    snapshot = await run_owned_thread(lambda: capture_workspace_state_snapshot(workspace=tmp_path), label="test-snapshot")
    await run_owned_thread(lambda: (tmp_path / "new.txt").write_bytes(b"actual changed workspace"), label="test-write")
    snapshot["workspace_type"] = "different-backend"
    inputs = _inputs({"run_determinism_class": "workspace", "workspace_state_snapshot": snapshot})
    before = deepcopy(inputs)
    with pytest.raises(ValueError, match="E_REPLAY_COMPATIBILITY_MISMATCH:") as failure:
        await run_owned_thread(lambda: evaluate_replay_compatibility(**inputs), label="test-compatibility")
    for field in ("file_count", "workspace_hash", "workspace_type"):
        assert "workspace_state_snapshot." + field in str(failure.value)
    assert inputs == before
    assert await run_owned_thread(lambda: (tmp_path / "new.txt").read_bytes(), label="test-read") == b"actual changed workspace"


@pytest.mark.integration
@pytest.mark.parametrize("case", ["missing", "file", "absent-path"])
async def test_workspace_location_refuses_native_non_directory_or_reports_missing(tmp_path, case):
    path = tmp_path / "target"
    if case == "file":
        await run_owned_thread(lambda: path.write_bytes(b"not a directory"), label="test-write")
    snapshot = {"workspace_path": "" if case == "absent-path" else str(path)}
    inputs = _inputs({"run_determinism_class": "external", "workspace_state_snapshot": snapshot})
    if case == "absent-path":
        report = await run_owned_thread(lambda: evaluate_replay_compatibility(**inputs), label="test-compatibility")
        assert "workspace_state_snapshot.workspace_path" in report["missing_contract_fields"]
        assert report["path"] == "degraded"
    else:
        with pytest.raises(ValueError, match="E_REPLAY_COMPATIBILITY_MISMATCH:workspace_state_snapshot.workspace_path"):
            await run_owned_thread(lambda: evaluate_replay_compatibility(**inputs), label="test-compatibility")


@pytest.mark.contract
async def test_optional_replay_keeps_lifecycle_and_missing_evidence_visible():
    inputs = _inputs({}, enforce=False)
    inputs["events"] = [{"kind": "run_started", "artifacts": []}]
    report = evaluate_replay_compatibility(**inputs)
    assert report["lifecycle_missing"] == ["run_finalized"]
    assert report["path"] == "degraded" and report["missing_contract_fields"]
    inputs["require_replay_artifact_completeness"] = True
    with pytest.raises(ValueError, match="E_REPLAY_INCOMPLETE:run_finalized"):
        evaluate_replay_compatibility(**inputs)


@pytest.mark.contract
async def test_empty_or_blank_ledger_versions_use_declared_legacy_default():
    assert resolve_ledger_schema_version([]) == "1.0"
    assert resolve_ledger_schema_version([{"ledger_schema_version": " "}]) == "1.0"
    with pytest.raises(ValueError, match="E_REPLAY_LEDGER_SCHEMA_INCOMPATIBLE:multiple_versions"):
        resolve_ledger_schema_version([{"ledger_schema_version": "1.0"}, {"ledger_schema_version": "2.0"}])
