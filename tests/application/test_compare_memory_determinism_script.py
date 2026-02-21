from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _trace(tool_result_fingerprint: str = "fp-1") -> dict:
    return {
        "run_id": "run-1",
        "workflow_id": "wf-1",
        "memory_snapshot_id": "snap-1",
        "visibility_mode": "read_only",
        "model_config_id": "model-1",
        "policy_set_id": "policy-1",
        "determinism_trace_schema_version": "memory.determinism_trace.v1",
        "events": [
            {
                "event_id": "evt-a",
                "index": 0,
                "role": "coder",
                "interceptor": "turn",
                "decision_type": "execute_turn",
                "tool_calls": [
                    {
                        "tool_name": "update_issue_status",
                        "tool_profile_version": "v1",
                        "normalized_args": {"status": "done"},
                        "normalization_version": "json-v1",
                        "tool_result_fingerprint": tool_result_fingerprint,
                        "side_effect_fingerprint": None,
                    }
                ],
                "guardrails_triggered": [],
                "retrieval_event_ids": ["ret-1"],
            }
        ],
        "output": {"output_type": "text", "output_shape_hash": "hash-1", "normalization_version": "json-v1"},
    }


def _retrieval(record_id: str = "r1") -> dict:
    return {
        "events": [
            {
                "retrieval_event_id": "ret-1",
                "run_id": "run-1",
                "event_id": "evt-a",
                "policy_id": "p",
                "policy_version": "v1",
                "query_normalization_version": "json-v1",
                "query_fingerprint": "q1",
                "retrieval_mode": "text_to_vector",
                "candidate_count": 1,
                "selected_records": [{"record_id": record_id, "record_type": "chunk", "score": 0.9, "rank": 1}],
                "applied_filters": {},
                "retrieval_trace_schema_version": "memory.retrieval_trace.v1",
            }
        ]
    }


def test_compare_memory_determinism_passes_for_equivalent_payloads(tmp_path: Path) -> None:
    left = tmp_path / "left.json"
    right = tmp_path / "right.json"
    left_ret = tmp_path / "left_ret.json"
    right_ret = tmp_path / "right_ret.json"
    left.write_text(json.dumps(_trace()) + "\n", encoding="utf-8")
    right.write_text(json.dumps(_trace()) + "\n", encoding="utf-8")
    left_ret.write_text(json.dumps(_retrieval()) + "\n", encoding="utf-8")
    right_ret.write_text(json.dumps(_retrieval()) + "\n", encoding="utf-8")

    result = subprocess.run(
        [
            "python",
            "scripts/compare_memory_determinism.py",
            "--left",
            str(left),
            "--right",
            str(right),
            "--left-retrieval",
            str(left_ret),
            "--right-retrieval",
            str(right_ret),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "PASS"


def test_compare_memory_determinism_fails_for_tool_fingerprint_mismatch(tmp_path: Path) -> None:
    left = tmp_path / "left.json"
    right = tmp_path / "right.json"
    left.write_text(json.dumps(_trace(tool_result_fingerprint="fp-a")) + "\n", encoding="utf-8")
    right.write_text(json.dumps(_trace(tool_result_fingerprint="fp-b")) + "\n", encoding="utf-8")

    result = subprocess.run(
        [
            "python",
            "scripts/compare_memory_determinism.py",
            "--left",
            str(left),
            "--right",
            str(right),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["status"] == "FAIL"
    assert any(item.startswith("tool_result_fingerprint_mismatch:0:0") for item in payload["failures"])
