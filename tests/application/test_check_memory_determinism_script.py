from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_check_memory_determinism_passes_with_minimal_valid_payloads(tmp_path: Path) -> None:
    trace = tmp_path / "memory_trace.json"
    retrieval = tmp_path / "memory_retrieval_trace.json"

    trace.write_text(
        json.dumps(
            {
                "run_id": "run-1",
                "workflow_id": "wf-1",
                "memory_snapshot_id": "snap-1",
                "visibility_mode": "read_only",
                "model_config_id": "modelcfg-1",
                "policy_set_id": "policy-1",
                "determinism_trace_schema_version": "memory.determinism_trace.v1",
                "events": [
                    {
                        "event_id": "evt-1",
                        "index": 0,
                        "role": "coder",
                        "interceptor": "before_prompt",
                        "decision_type": "prompt_build",
                        "tool_calls": [],
                        "guardrails_triggered": [],
                        "retrieval_event_ids": ["ret-1"],
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    retrieval.write_text(
        json.dumps(
            {
                "events": [
                    {
                        "retrieval_event_id": "ret-1",
                        "run_id": "run-1",
                        "event_id": "evt-1",
                        "policy_id": "p",
                        "policy_version": "v1",
                        "query_normalization_version": "json-v1",
                        "query_fingerprint": "abc",
                        "retrieval_mode": "text_to_vector",
                        "candidate_count": 1,
                        "selected_records": [],
                        "applied_filters": {},
                        "retrieval_trace_schema_version": "memory.retrieval_trace.v1",
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            "python",
            "scripts/check_memory_determinism.py",
            "--trace",
            str(trace),
            "--retrieval-trace",
            str(retrieval),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "PASS"


def test_check_memory_determinism_fails_on_missing_required_fields(tmp_path: Path) -> None:
    trace = tmp_path / "memory_trace.json"
    trace.write_text(json.dumps({"run_id": "run-1", "events": [{}]}) + "\n", encoding="utf-8")

    result = subprocess.run(
        [
            "python",
            "scripts/check_memory_determinism.py",
            "--trace",
            str(trace),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["status"] == "FAIL"
    assert "trace:missing:workflow_id" in payload["failures"]
    assert "trace:event:0:missing:event_id" in payload["failures"]
