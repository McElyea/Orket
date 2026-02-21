from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare two memory determinism traces for equivalence.")
    parser.add_argument("--left", required=True, help="Left memory trace JSON path.")
    parser.add_argument("--right", required=True, help="Right memory trace JSON path.")
    parser.add_argument("--left-retrieval", default="", help="Optional left retrieval trace JSON path.")
    parser.add_argument("--right-retrieval", default="", help="Optional right retrieval trace JSON path.")
    parser.add_argument("--out", default="", help="Optional output path for comparison report.")
    return parser.parse_args()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _as_retrieval_rows(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, dict):
        events = payload.get("events")
        if isinstance(events, list):
            return [row for row in events if isinstance(row, dict)]
        return [payload]
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    return []


def _compare_traces(left: Dict[str, Any], right: Dict[str, Any]) -> List[str]:
    failures: List[str] = []
    envelope_fields = ["workflow_id", "model_config_id", "policy_set_id", "memory_snapshot_id", "visibility_mode"]
    for field in envelope_fields:
        if left.get(field) != right.get(field):
            failures.append(f"envelope_mismatch:{field}")

    left_events = left.get("events") if isinstance(left.get("events"), list) else []
    right_events = right.get("events") if isinstance(right.get("events"), list) else []
    if len(left_events) != len(right_events):
        failures.append("events_length_mismatch")
        return failures

    for idx, (l_evt, r_evt) in enumerate(zip(left_events, right_events)):
        if not isinstance(l_evt, dict) or not isinstance(r_evt, dict):
            failures.append(f"event_type_mismatch:{idx}")
            continue
        for field in ["role", "interceptor", "decision_type"]:
            if l_evt.get(field) != r_evt.get(field):
                failures.append(f"event_mismatch:{idx}:{field}")

        l_tools = l_evt.get("tool_calls") if isinstance(l_evt.get("tool_calls"), list) else []
        r_tools = r_evt.get("tool_calls") if isinstance(r_evt.get("tool_calls"), list) else []
        if len(l_tools) != len(r_tools):
            failures.append(f"tool_count_mismatch:{idx}")
            continue
        for tool_idx, (l_tool, r_tool) in enumerate(zip(l_tools, r_tools)):
            if not isinstance(l_tool, dict) or not isinstance(r_tool, dict):
                failures.append(f"tool_type_mismatch:{idx}:{tool_idx}")
                continue
            if l_tool.get("tool_name") != r_tool.get("tool_name"):
                failures.append(f"tool_name_mismatch:{idx}:{tool_idx}")
            if l_tool.get("normalized_args") != r_tool.get("normalized_args"):
                failures.append(f"tool_args_mismatch:{idx}:{tool_idx}")
            if l_tool.get("tool_result_fingerprint") != r_tool.get("tool_result_fingerprint"):
                failures.append(f"tool_result_fingerprint_mismatch:{idx}:{tool_idx}")
            if l_tool.get("side_effect_fingerprint") != r_tool.get("side_effect_fingerprint"):
                failures.append(f"side_effect_fingerprint_mismatch:{idx}:{tool_idx}")

        l_guard = sorted([str(x) for x in (l_evt.get("guardrails_triggered") or [])])
        r_guard = sorted([str(x) for x in (r_evt.get("guardrails_triggered") or [])])
        if l_guard != r_guard:
            failures.append(f"guardrails_mismatch:{idx}")

    l_out = left.get("output") if isinstance(left.get("output"), dict) else {}
    r_out = right.get("output") if isinstance(right.get("output"), dict) else {}
    if l_out.get("output_type") != r_out.get("output_type"):
        failures.append("output_mismatch:output_type")
    if l_out.get("output_shape_hash") != r_out.get("output_shape_hash"):
        failures.append("output_mismatch:output_shape_hash")
    return failures


def _compare_retrieval(left_rows: List[Dict[str, Any]], right_rows: List[Dict[str, Any]]) -> List[str]:
    failures: List[str] = []
    if not left_rows and not right_rows:
        return failures
    if len(left_rows) != len(right_rows):
        return ["retrieval_length_mismatch"]
    for idx, (l_row, r_row) in enumerate(zip(left_rows, right_rows)):
        for field in ["policy_id", "policy_version", "query_fingerprint", "query_normalization_version", "retrieval_mode"]:
            if l_row.get(field) != r_row.get(field):
                failures.append(f"retrieval_mismatch:{idx}:{field}")
        l_ids = [str((rec or {}).get("record_id", "")) for rec in (l_row.get("selected_records") or []) if isinstance(rec, dict)]
        r_ids = [str((rec or {}).get("record_id", "")) for rec in (r_row.get("selected_records") or []) if isinstance(rec, dict)]
        if l_ids != r_ids:
            failures.append(f"retrieval_record_order_mismatch:{idx}")
    return failures


def main() -> int:
    args = _parse_args()
    left = _load_json(Path(args.left))
    right = _load_json(Path(args.right))
    if not isinstance(left, dict) or not isinstance(right, dict):
        raise SystemExit("left and right traces must be JSON objects")

    failures = _compare_traces(left, right)

    left_ret_rows: List[Dict[str, Any]] = []
    right_ret_rows: List[Dict[str, Any]] = []
    if str(args.left_retrieval or "").strip() and str(args.right_retrieval or "").strip():
        left_ret_rows = _as_retrieval_rows(_load_json(Path(args.left_retrieval)))
        right_ret_rows = _as_retrieval_rows(_load_json(Path(args.right_retrieval)))
        failures.extend(_compare_retrieval(left_ret_rows, right_ret_rows))

    report = {
        "status": "PASS" if not failures else "FAIL",
        "left": str(Path(args.left)).replace("\\", "/"),
        "right": str(Path(args.right)).replace("\\", "/"),
        "left_retrieval_rows": len(left_ret_rows),
        "right_retrieval_rows": len(right_ret_rows),
        "failures": failures,
    }
    text = json.dumps(report, indent=2)
    print(text)
    if str(args.out or "").strip():
        out_path = Path(str(args.out))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
