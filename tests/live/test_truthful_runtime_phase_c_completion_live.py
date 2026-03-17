from __future__ import annotations

import json
from pathlib import Path

import pytest

from orket.adapters.tools.families.filesystem import FileSystemTools
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
async def test_phase_c_live_required_source_attribution_blocks_missing_receipt(
    tmp_path: Path,
    monkeypatch,
) -> None:
    if not _live_enabled():
        pytest.skip("Set ORKET_LIVE_ACCEPTANCE=1 to run live Phase C proof.")

    monkeypatch.setenv("ORKET_RUN_LEDGER_MODE", "protocol")
    monkeypatch.setenv("ORKET_DISABLE_SANDBOX", "1")
    root = tmp_path
    workspace = root / "workspace"
    workspace.mkdir()
    (workspace / "agent_output").mkdir()
    db_path = str(root / "phase_c_blocked_live.db")
    write_core_acceptance_assets(
        root,
        epic_id="phase_c_blocked_live",
        environment_model=_live_model(),
        truthful_runtime={"source_attribution_mode": "required"},
        source_attribution_receipt_task=False,
    )

    engine = OrchestrationEngine(workspace, department="core", db_path=db_path, config_root=root)
    await engine.run_card("phase_c_blocked_live")

    run_roots = _run_roots(workspace)
    assert len(run_roots) == 1
    run_summary = _read_json(run_roots[0] / "run_summary.json")
    packet2 = run_summary["truthful_runtime_packet2"]

    print(
        "[live][phase-c][blocked] "
        f"run_id={run_summary['run_id']} status={run_summary['status']} "
        f"failure_reason={run_summary['failure_reason']}"
    )
    assert run_summary["status"] == "terminal_failure"
    assert run_summary["failure_reason"] == "source_attribution_receipt_missing"
    assert packet2["source_attribution"]["synthesis_status"] == "blocked"
    assert packet2["source_attribution"]["missing_requirements"] == ["source_attribution_receipt_missing"]


@pytest.mark.asyncio
async def test_phase_c_live_required_source_attribution_verifies_receipt(
    tmp_path: Path,
    monkeypatch,
) -> None:
    if not _live_enabled():
        pytest.skip("Set ORKET_LIVE_ACCEPTANCE=1 to run live Phase C proof.")

    monkeypatch.setenv("ORKET_RUN_LEDGER_MODE", "protocol")
    monkeypatch.setenv("ORKET_DISABLE_SANDBOX", "1")
    root = tmp_path
    workspace = root / "workspace"
    workspace.mkdir()
    (workspace / "agent_output").mkdir()
    db_path = str(root / "phase_c_verified_live.db")
    write_core_acceptance_assets(
        root,
        epic_id="phase_c_verified_live",
        environment_model=_live_model(),
        truthful_runtime={"source_attribution_mode": "required"},
        source_attribution_receipt_task=True,
    )

    engine = OrchestrationEngine(workspace, department="core", db_path=db_path, config_root=root)
    await engine.run_card("phase_c_verified_live")

    run_roots = _run_roots(workspace)
    assert len(run_roots) == 1
    run_summary = _read_json(run_roots[0] / "run_summary.json")
    packet1 = run_summary["truthful_runtime_packet1"]
    packet2 = run_summary["truthful_runtime_packet2"]

    print(
        "[live][phase-c][verified] "
        f"run_id={run_summary['run_id']} status={run_summary['status']} "
        f"source_status={packet2['source_attribution']['synthesis_status']}"
    )
    assert run_summary["status"] == "done"
    assert packet1["provenance"]["primary_output_id"] == "agent_output/main.py"
    assert packet2["source_attribution"]["synthesis_status"] == "verified"
    assert packet2["source_attribution"]["claim_count"] >= 1
    assert packet2["source_attribution"]["source_count"] >= 3
    assert packet2["narration_to_effect_audit"]["missing_effect_count"] == 0
    surfaces = {row["surface"] for row in packet2["idempotency"]["surfaces"]}
    assert "artifact_write" in surfaces
    assert "status_update" in surfaces
    assert "source_attribution_receipt" in surfaces


@pytest.mark.asyncio
async def test_phase_c_live_narration_effect_audit_detects_missing_source_receipt_effect(
    tmp_path: Path,
    monkeypatch,
) -> None:
    if not _live_enabled():
        pytest.skip("Set ORKET_LIVE_ACCEPTANCE=1 to run live Phase C proof.")

    monkeypatch.setenv("ORKET_RUN_LEDGER_MODE", "protocol")
    monkeypatch.setenv("ORKET_DISABLE_SANDBOX", "1")
    original_write_file = FileSystemTools.write_file

    async def _drop_source_receipt_write(self, args, context=None):
        path = str((args or {}).get("path") or "").replace("\\", "/").strip().lower()
        if path.endswith("agent_output/source_attribution_receipt.json"):
            return {"ok": True, "path": str((self.workspace_root / "agent_output" / "source_attribution_receipt.json"))}
        return await original_write_file(self, args, context=context)

    monkeypatch.setattr(FileSystemTools, "write_file", _drop_source_receipt_write)

    root = tmp_path
    workspace = root / "workspace"
    workspace.mkdir()
    (workspace / "agent_output").mkdir()
    db_path = str(root / "phase_c_missing_effect_live.db")
    write_core_acceptance_assets(
        root,
        epic_id="phase_c_missing_effect_live",
        environment_model=_live_model(),
        truthful_runtime={"source_attribution_mode": "optional"},
        source_attribution_receipt_task=True,
    )

    engine = OrchestrationEngine(workspace, department="core", db_path=db_path, config_root=root)
    await engine.run_card("phase_c_missing_effect_live")

    run_roots = _run_roots(workspace)
    assert len(run_roots) == 1
    run_summary = _read_json(run_roots[0] / "run_summary.json")
    packet2 = run_summary["truthful_runtime_packet2"]
    missing_entry = next(
        row
        for row in packet2["narration_to_effect_audit"]["entries"]
        if row["effect_target"] == "agent_output/source_attribution_receipt.json"
    )

    print(
        "[live][phase-c][missing-effect] "
        f"run_id={run_summary['run_id']} status={run_summary['status']} "
        f"audit_failure={missing_entry['failure_reason']}"
    )
    assert run_summary["status"] == "done"
    assert missing_entry["audit_status"] == "missing"
    assert missing_entry["failure_reason"] == "workspace_artifact_missing"
    assert packet2["source_attribution"]["synthesis_status"] == "optional_unverified"
