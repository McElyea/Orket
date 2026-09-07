from __future__ import annotations

import json
from pathlib import Path

import pytest

from orket.application.services.governed_run_demo_service import (
    inspect_governed_run_bundle,
    replay_governed_run_bundle,
    run_governed_run_scenario,
)


def _write_test_scenario(tmp_path: Path) -> Path:
    example_dir = tmp_path / "demo-files"
    example_dir.mkdir()
    (example_dir / "README.md").write_text("demo\n", encoding="utf-8")
    scenario = tmp_path / "scenario.yaml"
    scenario.write_text(
        """
schema_version: governed_run.scenario.v1
name: governed-run-test
run_id: governed-run-test
started_at: "2026-07-12T00:00:00Z"
completed_at: "2026-07-12T00:00:01Z"
model:
  kind: simulated
policy:
  shell_allowlist: []
actions:
  - id: inspect-files
    kind: list
    target: demo-files
    intent: Wants to inspect files
  - id: edit-config
    kind: edit
    target: config.yaml
    intent: Wants to edit config.yaml
  - id: run-shell-command
    kind: shell
    command: rm -rf tmp/demo-cache
    intent: Wants to run shell command
""".lstrip(),
        encoding="utf-8",
    )
    return scenario


@pytest.mark.asyncio
async def test_governed_run_writes_evidence_bundle_and_blocks_side_effects(tmp_path: Path) -> None:
    """Layer: integration. Proves a local scenario emits inspectable evidence without risky side effects."""
    scenario = _write_test_scenario(tmp_path)

    result = await run_governed_run_scenario(scenario, workspace_root=tmp_path)

    run_dir = tmp_path / ".runs" / "governed-run-test"
    evidence_path = run_dir / "evidence.json"
    transcript_path = run_dir / "transcript.md"
    replay_path = run_dir / "replay.json"
    summary_path = run_dir / "summary.md"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    replay = json.loads(replay_path.read_text(encoding="utf-8"))

    assert result["run_id"] == "governed-run-test"
    assert evidence_path.is_file()
    assert transcript_path.is_file()
    assert replay_path.is_file()
    assert summary_path.is_file()
    assert evidence["totals"] == {"allowed": 1, "denied": 1, "requires_approval": 1, "side_effects_occurred": 0}
    assert [action["resulting_status"] for action in evidence["proposed_actions"]] == [
        "success",
        "blocked_pending_approval",
        "blocked",
    ]
    assert evidence["proposed_actions"][0]["observation"]["entries"] == ["demo-files/README.md"]
    assert (tmp_path / "config.yaml").exists() is False
    assert replay["replay_status"] == "success"
    assert replay["side_effects_replayed"] is False

    inspection = await inspect_governed_run_bundle(run_dir)
    replay_result = await replay_governed_run_bundle(run_dir)

    assert inspection["ok"] is True
    assert [action["decision"] for action in inspection["actions"]] == ["allow", "requires_approval", "deny"]
    assert replay_result["ok"] is True
    assert all(action["decision_matches_evidence"] for action in replay_result["reconstructed_actions"])
