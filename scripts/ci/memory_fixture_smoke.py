from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Write deterministic memory trace smoke fixtures for CI workflows.")
    parser.add_argument("--profile", choices=("quality", "nightly"), default="quality")
    parser.add_argument("--out-dir", default="benchmarks/results/benchmarks/memory")
    return parser


def _quality_payloads() -> tuple[dict[str, Any], dict[str, Any]]:
    trace = {
        "run_id": "quality-memory-run",
        "workflow_id": "quality-memory-workflow",
        "memory_snapshot_id": "snapshot-0",
        "visibility_mode": "read_only",
        "model_config_id": "model-config",
        "policy_set_id": "policy-set",
        "determinism_trace_schema_version": "memory.determinism_trace.v1",
        "events": [
            {
                "event_id": "evt-0",
                "index": 0,
                "role": "coder",
                "interceptor": "before_prompt",
                "decision_type": "prompt_build",
                "tool_calls": [],
                "guardrails_triggered": [],
                "retrieval_event_ids": ["ret-0"],
            }
        ],
    }
    retrieval = {
        "events": [
            {
                "retrieval_event_id": "ret-0",
                "run_id": "quality-memory-run",
                "event_id": "evt-0",
                "policy_id": "retrieval-policy",
                "policy_version": "v1",
                "query_normalization_version": "json-v1",
                "query_fingerprint": "abc123",
                "retrieval_mode": "text_to_vector",
                "candidate_count": 1,
                "selected_records": [],
                "applied_filters": {},
                "retrieval_trace_schema_version": "memory.retrieval_trace.v1",
            }
        ]
    }
    return trace, retrieval


def _nightly_payloads() -> tuple[dict[str, Any], dict[str, Any]]:
    trace = {
        "run_id": "nightly-memory-fixture",
        "workflow_id": "nightly_benchmark",
        "memory_snapshot_id": "snapshot-fixture",
        "visibility_mode": "read_only",
        "model_config_id": "fixture-model",
        "policy_set_id": "fixture-policy",
        "determinism_trace_schema_version": "memory.determinism_trace.v1",
        "events": [
            {
                "event_id": "evt-0",
                "index": 0,
                "role": "bench",
                "interceptor": "before_prompt",
                "decision_type": "prompt_ready",
                "tool_calls": [],
                "guardrails_triggered": [],
                "retrieval_event_ids": ["ret-0"],
            }
        ],
        "output": {
            "output_type": "text",
            "output_shape_hash": "fixture-shape-hash",
            "normalization_version": "json-v1",
        },
        "metadata": {"truncated": False},
    }
    retrieval = {
        "events": [
            {
                "retrieval_event_id": "ret-0",
                "run_id": "nightly-memory-fixture",
                "event_id": "evt-0",
                "policy_id": "fixture-policy",
                "policy_version": "v1",
                "query_normalization_version": "json-v1",
                "query_fingerprint": "fixture-query",
                "retrieval_mode": "text_to_vector",
                "candidate_count": 0,
                "selected_records": [],
                "applied_filters": {},
                "retrieval_trace_schema_version": "memory.retrieval_trace.v1",
            }
        ],
        "retrieval_trace_schema_version": "memory.retrieval_trace.v1",
        "metadata": {"truncated": False},
    }
    return trace, retrieval


def write_fixtures(*, out_dir: Path, profile: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    trace, retrieval = _nightly_payloads() if profile == "nightly" else _quality_payloads()
    payloads = {
        "memory_trace_fixture_left.json": trace,
        "memory_retrieval_trace_fixture_left.json": retrieval,
        "memory_trace_fixture_right.json": trace,
        "memory_retrieval_trace_fixture_right.json": retrieval,
    }
    for filename, payload in payloads.items():
        (out_dir / filename).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    write_fixtures(out_dir=Path(str(args.out_dir)), profile=str(args.profile))
    return 0


if __name__ == "__main__":
    sys.exit(main())
