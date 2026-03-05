from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_ENVELOPE_FIELDS = [
    "run_id",
    "workflow_id",
    "memory_snapshot_id",
    "visibility_mode",
    "model_config_id",
    "policy_set_id",
    "determinism_trace_schema_version",
]

REQUIRED_EVENT_FIELDS = [
    "event_id",
    "index",
    "role",
    "interceptor",
    "decision_type",
    "tool_calls",
    "guardrails_triggered",
    "retrieval_event_ids",
]

REQUIRED_RETRIEVAL_FIELDS = [
    "retrieval_event_id",
    "run_id",
    "event_id",
    "policy_id",
    "policy_version",
    "query_normalization_version",
    "query_fingerprint",
    "retrieval_mode",
    "candidate_count",
    "selected_records",
    "applied_filters",
    "retrieval_trace_schema_version",
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate memory determinism trace contracts.")
    parser.add_argument("--trace", required=True, help="Path to determinism trace JSON artifact.")
    parser.add_argument(
        "--retrieval-trace",
        default="",
        help="Optional path to retrieval trace JSON artifact (object or array).",
    )
    parser.add_argument("--out", default="", help="Optional output path for report JSON.")
    parser.add_argument(
        "--max-trace-bytes",
        type=int,
        default=10 * 1024 * 1024,
        help="Maximum allowed size per trace artifact before truncation marker is required.",
    )
    return parser.parse_args()


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _append_missing(prefix: str, payload: dict[str, Any], required: list[str], failures: list[str]) -> None:
    for field in required:
        if field not in payload:
            failures.append(f"{prefix}:missing:{field}")


def _validate_trace(trace_payload: dict[str, Any], failures: list[str]) -> None:
    _append_missing("trace", trace_payload, REQUIRED_ENVELOPE_FIELDS, failures)

    events = trace_payload.get("events")
    if not isinstance(events, list):
        failures.append("trace:missing:events")
        return

    for idx, event in enumerate(events):
        if not isinstance(event, dict):
            failures.append(f"trace:event:{idx}:invalid_type")
            continue
        _append_missing(f"trace:event:{idx}", event, REQUIRED_EVENT_FIELDS, failures)


def _validate_retrieval_trace(payload: Any, failures: list[str]) -> None:
    rows: list[Any]
    if isinstance(payload, dict):
        if isinstance(payload.get("events"), list):
            rows = payload.get("events") or []
        else:
            rows = [payload]
    elif isinstance(payload, list):
        rows = payload
    else:
        failures.append("retrieval_trace:invalid_type")
        return

    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            failures.append(f"retrieval_trace:event:{idx}:invalid_type")
            continue
        _append_missing(f"retrieval_trace:event:{idx}", row, REQUIRED_RETRIEVAL_FIELDS, failures)


def main() -> int:
    args = _parse_args()
    failures: list[str] = []

    trace_path = Path(args.trace)
    trace_size = trace_path.stat().st_size
    trace_payload = _load(trace_path)
    if not isinstance(trace_payload, dict):
        failures.append("trace:invalid_type")
    else:
        _validate_trace(trace_payload, failures)
        if trace_size > int(args.max_trace_bytes):
            metadata = trace_payload.get("metadata") if isinstance(trace_payload.get("metadata"), dict) else {}
            if metadata.get("truncated") is not True:
                failures.append("trace:missing:truncation_marker")

    retrieval_path_text = str(args.retrieval_trace or "").strip()
    retrieval_checked = ""
    retrieval_size = 0
    if retrieval_path_text:
        retrieval_path = Path(retrieval_path_text)
        retrieval_checked = str(retrieval_path).replace("\\", "/")
        retrieval_size = retrieval_path.stat().st_size
        retrieval_payload = _load(retrieval_path)
        _validate_retrieval_trace(retrieval_payload, failures)
        if retrieval_size > int(args.max_trace_bytes):
            metadata = retrieval_payload.get("metadata") if isinstance(retrieval_payload, dict) else {}
            if metadata.get("truncated") is not True:
                failures.append("retrieval_trace:missing:truncation_marker")

    report = {
        "status": "PASS" if not failures else "FAIL",
        "trace": str(trace_path).replace("\\", "/"),
        "trace_size_bytes": trace_size,
        "retrieval_trace": retrieval_checked,
        "retrieval_trace_size_bytes": retrieval_size,
        "failures": failures,
    }
    text = json.dumps(report, indent=2)
    print(text)

    out_text = str(args.out or "").strip()
    if out_text:
        out_path = Path(out_text)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
