from __future__ import annotations

import json
from pathlib import Path

from orket.logging import get_member_metrics, log_event


def _load_last_log_record(path: Path) -> dict:
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert lines
    return json.loads(lines[-1])


def test_log_event_adds_runtime_event_envelope_and_artifact(tmp_path: Path) -> None:
    log_event(
        "turn_complete",
        {
            "session_id": "run-1",
            "issue_id": "ISS-1",
            "role": "architect",
            "turn_index": 2,
            "turn_trace_id": "run-1:ISS-1:architect:2",
            "selected_model": "qwen2.5-coder:14b",
            "prompt_id": "role.architect+dialect.generic",
            "prompt_version": "1.0.0/1.0.0",
            "prompt_checksum": "abc123",
            "resolver_policy": "resolver_v1",
            "selection_policy": "stable",
            "duration_ms": 321,
            "tokens": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        },
        workspace=tmp_path,
    )

    record = _load_last_log_record(tmp_path / "orket.log")
    runtime_event = record["data"]["runtime_event"]
    assert runtime_event["schema_version"] == "v1"
    assert runtime_event["event"] == "turn_complete"
    assert runtime_event["session_id"] == "run-1"
    assert runtime_event["issue_id"] == "ISS-1"
    assert runtime_event["turn_index"] == 2
    assert runtime_event["duration_ms"] == 321

    runtime_events_path = tmp_path / "agent_output" / "observability" / "runtime_events.jsonl"
    lines = runtime_events_path.read_text(encoding="utf-8").strip().splitlines()
    assert lines
    artifact_event = json.loads(lines[-1])
    assert artifact_event["schema_version"] == "v1"
    assert artifact_event["session_id"] == "run-1"


def test_log_event_runtime_artifact_skips_when_session_missing(tmp_path: Path) -> None:
    log_event("generic_event", {"role": "system"}, workspace=tmp_path)
    runtime_events_path = tmp_path / "agent_output" / "observability" / "runtime_events.jsonl"
    assert not runtime_events_path.exists()


def test_log_event_isolated_per_workspace(tmp_path: Path) -> None:
    workspace_a = tmp_path / "workspace-a"
    workspace_b = tmp_path / "workspace-b"

    log_event("event_a", {"role": "coder"}, workspace=workspace_a)
    log_event("event_b", {"role": "reviewer"}, workspace=workspace_b)

    lines_a = (workspace_a / "orket.log").read_text(encoding="utf-8").strip().splitlines()
    lines_b = (workspace_b / "orket.log").read_text(encoding="utf-8").strip().splitlines()

    assert lines_a and lines_b
    assert any('"event": "event_a"' in line for line in lines_a)
    assert not any('"event": "event_b"' in line for line in lines_a)
    assert any('"event": "event_b"' in line for line in lines_b)
    assert not any('"event": "event_a"' in line for line in lines_b)


def test_get_member_metrics_returns_aggregated_roles(tmp_path: Path) -> None:
    log_path = tmp_path / "orket.log"
    log_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "event": "model_usage",
                        "role": "coder",
                        "data": {"total_tokens": 13},
                    }
                ),
                json.dumps(
                    {
                        "event": "tool_call",
                        "role": "coder",
                        "data": {
                            "tool": "write_file",
                            "args": {"path": "app.py", "content": "a\nb"},
                        },
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    metrics = get_member_metrics(tmp_path)
    assert metrics["coder"]["tokens"] == 13
    assert metrics["coder"]["lines_written"] == 2
