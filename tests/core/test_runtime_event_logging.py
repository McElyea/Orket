from __future__ import annotations

import json
import logging
import queue
from pathlib import Path

import orket.logging as logging_module
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


def test_log_event_persists_structured_determinism_violation_fields(tmp_path: Path) -> None:
    log_event(
        "determinism_violation",
        {
            "session_id": "run-1",
            "issue_id": "ISS-1",
            "role": "coder",
            "turn_index": 2,
            "tool": "write_file",
            "error": "E_DETERMINISM_VIOLATION: write_file declared pure but observed side effects",
            "error_code": "E_DETERMINISM_VIOLATION",
            "determinism_class": "pure",
            "capability_profile": "workspace",
            "tool_contract_version": "1.0.0",
            "side_effect_signal_keys": ["tool_name_side_effect", "changed_files"],
        },
        workspace=tmp_path,
    )

    runtime_events_path = tmp_path / "agent_output" / "observability" / "runtime_events.jsonl"
    lines = runtime_events_path.read_text(encoding="utf-8").strip().splitlines()
    assert lines
    artifact_event = json.loads(lines[-1])
    assert artifact_event["event"] == "determinism_violation"
    assert artifact_event["error_code"] == "E_DETERMINISM_VIOLATION"
    assert artifact_event["determinism_class"] == "pure"
    assert artifact_event["capability_profile"] == "workspace"
    assert artifact_event["tool_contract_version"] == "1.0.0"
    assert artifact_event["side_effect_signal_keys"] == ["tool_name_side_effect", "changed_files"]


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


def test_log_event_routes_legacy_level_through_stdlib_logger(tmp_path: Path, monkeypatch) -> None:
    """Layer: contract. Verifies legacy level routing drives stdlib logging and a first-class log level field."""
    monkeypatch.chdir(tmp_path)
    logger = logging.getLogger("orket")
    captured: list[logging.LogRecord] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured.append(record)

    handler = _Capture()
    logger.addHandler(handler)
    try:
        log_event("error", "webhook_db", "legacy_event", {"message": "boom"})
    finally:
        logger.removeHandler(handler)

    record = _load_last_log_record(tmp_path / "workspace" / "default" / "orket.log")
    assert captured
    assert captured[-1].levelno == logging.ERROR
    assert captured[-1].orket_record["level"] == "error"
    assert record["level"] == "error"
    assert record["role"] == "webhook_db"
    assert record["event"] == "legacy_event"


def test_log_write_queue_drops_when_full_without_blocking_event_loop(tmp_path: Path, monkeypatch) -> None:
    """Layer: unit. Verifies async-reachable log writes use bounded lossy backpressure."""
    monkeypatch.setattr(logging_module, "_log_write_queue", queue.Queue(maxsize=1))
    monkeypatch.setattr(logging_module, "_dropped_log_entries", 0)
    monkeypatch.setattr(logging_module, "_start_log_writer", lambda: None)
    monkeypatch.setattr(logging_module, "_running_on_event_loop", lambda: True)

    log_path = tmp_path / "orket.log"
    logging_module._append_json_record(log_path, {"event": "queued"})
    logging_module._append_json_record(log_path, {"event": "dropped"})

    assert logging_module._log_write_queue.qsize() == 1
    assert logging_module.dropped_log_entry_count() == 1
    assert not log_path.exists()


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


def test_log_event_persists_sdk_capability_authorization_fields(tmp_path: Path) -> None:
    log_event(
        "sdk_capability_call_blocked",
        {
            "session_id": "sdk-run-1",
            "run_id": "sdk-run-1",
            "extension_id": "demo.ext",
            "workload_id": "sdk_v1",
            "capability_id": "memory.write",
            "capability_family": "memory_write",
            "authorization_basis": "host_authorized_capability_registry_v1",
            "declared": True,
            "admitted": False,
            "side_effect_observed": False,
            "denial_class": "denied",
        },
        workspace=tmp_path,
    )

    artifact_event = _load_last_log_record(tmp_path / "agent_output" / "observability" / "runtime_events.jsonl")
    assert artifact_event["event"] == "sdk_capability_call_blocked"
    assert artifact_event["run_id"] == "sdk-run-1"
    assert artifact_event["extension_id"] == "demo.ext"
    assert artifact_event["workload_id"] == "sdk_v1"
    assert artifact_event["capability_id"] == "memory.write"
    assert artifact_event["capability_family"] == "memory_write"
    assert artifact_event["authorization_basis"] == "host_authorized_capability_registry_v1"
    assert artifact_event["declared"] is True
    assert artifact_event["admitted"] is False
    assert artifact_event["side_effect_observed"] is False
    assert artifact_event["denial_class"] == "denied"
