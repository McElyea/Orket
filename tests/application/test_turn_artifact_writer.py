from __future__ import annotations

import json
from pathlib import Path

from orket.application.workflows.turn_artifact_writer import TurnArtifactWriter


def test_turn_artifact_writer_replay_round_trip(tmp_path: Path) -> None:
    writer = TurnArtifactWriter(tmp_path)
    payload = {"ok": True, "value": 7}
    args = {"path": "agent_output/main.py"}

    writer.persist_tool_result(
        session_id="s1",
        issue_id="ISSUE-1",
        role_name="coder",
        turn_index=1,
        tool_name="write_file",
        tool_args=args,
        result=payload,
    )

    loaded = writer.load_replay_tool_result(
        session_id="s1",
        issue_id="ISSUE-1",
        role_name="coder",
        turn_index=1,
        tool_name="write_file",
        tool_args=args,
        resume_mode=True,
    )

    assert loaded == payload


def test_turn_artifact_writer_checkpoint_writes_file(tmp_path: Path) -> None:
    writer = TurnArtifactWriter(tmp_path)
    writer.write_turn_checkpoint(
        session_id="s1",
        issue_id="ISSUE-1",
        role_name="coder",
        turn_index=2,
        prompt_hash="abc123",
        selected_model="test-model",
        tool_calls=[],
        state_delta={"from": "doing", "to": "done"},
        prompt_metadata={"prompt_id": "p1"},
    )

    out_dir = tmp_path / "observability" / "s1" / "ISSUE-1" / "002_coder"
    checkpoint = out_dir / "checkpoint.json"
    assert checkpoint.exists()
    data = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert data["prompt_hash"] == "abc123"
