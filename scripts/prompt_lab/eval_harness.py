from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Tuple


def _iter_turn_dirs(observability_root: Path):
    if not observability_root.exists():
        return
    for run_dir in observability_root.iterdir():
        if not run_dir.is_dir():
            continue
        for issue_dir in run_dir.iterdir():
            if not issue_dir.is_dir():
                continue
            for turn_dir in issue_dir.iterdir():
                if turn_dir.is_dir():
                    yield run_dir.name, issue_dir.name, turn_dir


def _read_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, ValueError, TypeError):
        return None


def evaluate(observability_root: Path, log_path: Path) -> Dict[str, float]:
    total_turns = 0
    turns_with_tools = 0
    required_action_complete = 0
    status_progressions = 0
    guard_decisions = 0

    for _run_id, _issue_id, turn_dir in _iter_turn_dirs(observability_root):
        total_turns += 1
        tools = _read_json(turn_dir / "parsed_tool_calls.json") or []
        checkpoint = _read_json(turn_dir / "checkpoint.json") or {}

        if tools:
            turns_with_tools += 1
        if tools and any((t or {}).get("tool") == "update_issue_status" for t in tools):
            required_action_complete += 1

        state_delta = checkpoint.get("state_delta") or {}
        if state_delta.get("from") and state_delta.get("to") and state_delta["from"] != state_delta["to"]:
            status_progressions += 1

    if log_path.exists():
        for line in log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("event") in {"guard_approved", "guard_rejected", "guard_requested_changes"}:
                guard_decisions += 1

    if total_turns == 0:
        return {
            "turn_count": 0.0,
            "tool_parse_rate": 0.0,
            "required_action_completion_rate": 0.0,
            "status_progression_rate": 0.0,
            "guard_decision_reach_rate": 0.0,
        }

    denom = float(total_turns)
    return {
        "turn_count": float(total_turns),
        "tool_parse_rate": turns_with_tools / denom,
        "required_action_completion_rate": required_action_complete / denom,
        "status_progression_rate": status_progressions / denom,
        "guard_decision_reach_rate": guard_decisions / denom,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate prompt quality metrics from observability artifacts.")
    parser.add_argument("--observability-root", default="workspace/default/observability")
    parser.add_argument("--log", default="workspace/default/orket.log")
    parser.add_argument("--out", default="benchmarks/results/prompt_eval_metrics.json")
    args = parser.parse_args()

    metrics = evaluate(Path(args.observability_root), Path(args.log))
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(metrics, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
