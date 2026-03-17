from __future__ import annotations

import json
from pathlib import Path

import pytest

from orket.adapters.storage.protocol_append_only_ledger import AppendOnlyRunLedger
from orket.orchestration.engine import OrchestrationEngine
from orket.runtime.live_acceptance_assets import write_core_acceptance_assets
from tests.live.test_runtime_stability_closeout_live import _live_enabled, _live_model

pytestmark = pytest.mark.end_to_end


def _read_json(path: Path) -> dict:
    return json.loads(path.read_bytes().decode("utf-8"))


def _run_roots(workspace: Path) -> list[Path]:
    runs_root = workspace / "runs"
    if not runs_root.exists():
        return []
    return sorted(path for path in runs_root.iterdir() if path.is_dir())


@pytest.mark.asyncio
async def test_artifact_provenance_live_acceptance_run_records_generated_files(tmp_path: Path, monkeypatch) -> None:
    if not _live_enabled():
        pytest.skip("Set ORKET_LIVE_ACCEPTANCE=1 to run live artifact provenance proof.")

    monkeypatch.setenv("ORKET_RUN_LEDGER_MODE", "protocol")
    monkeypatch.setenv("ORKET_DISABLE_SANDBOX", "1")
    root = tmp_path
    workspace = root / "workspace"
    workspace.mkdir()
    (workspace / "agent_output").mkdir()
    (workspace / "verification").mkdir()
    db_path = str(root / "artifact_provenance_live.db")
    write_core_acceptance_assets(
        root,
        epic_id="artifact_provenance_live",
        environment_model=_live_model(),
    )

    engine = OrchestrationEngine(workspace, department="core", db_path=db_path, config_root=root)
    await engine.run_card("artifact_provenance_live")

    run_roots = _run_roots(workspace)
    assert len(run_roots) == 1
    run_root = run_roots[0]
    run_summary = _read_json(run_root / "run_summary.json")
    artifact_provenance = run_summary["truthful_runtime_artifact_provenance"]
    entries = artifact_provenance["artifacts"]
    paths = [entry["artifact_path"] for entry in entries]

    print(
        "[live][artifact-provenance] "
        f"run_id={run_summary['run_id']} status={run_summary['status']} "
        f"artifact_count={len(entries)}"
    )
    assert run_summary["status"] == "done"
    assert "agent_output/requirements.txt" in paths
    assert "agent_output/design.txt" in paths
    assert "agent_output/main.py" in paths

    expected_types = {
        "agent_output/requirements.txt": "requirements_document",
        "agent_output/design.txt": "design_document",
        "agent_output/main.py": "source_code",
    }
    for path, artifact_type in expected_types.items():
        entry = next(row for row in entries if row["artifact_path"] == path)
        assert entry["artifact_type"] == artifact_type
        assert entry["generator"] == "tool.write_file"
        assert entry["truth_classification"] == "direct"
        assert entry["source_hash"]
        assert entry["produced_at"]
        assert entry["step_id"]
        assert entry["operation_id"]
        assert entry["issue_id"]
        assert entry["role_name"]
        assert entry["turn_index"] >= 1

    protocol_events = AppendOnlyRunLedger(run_root / "events.log").replay_events()
    artifact_fact = next(row for row in protocol_events if row["kind"] == "artifact_provenance_fact")
    finalized = next(row for row in reversed(protocol_events) if row["kind"] == "run_finalized")
    assert artifact_fact["artifact_provenance_facts"]["artifacts"] == entries
    assert finalized["summary"]["truthful_runtime_artifact_provenance"] == artifact_provenance
