from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:  # pragma: no cover - script execution bootstrap
    sys.path.insert(0, str(PROJECT_ROOT))

from orket.adapters.storage.protocol_append_only_ledger import AppendOnlyRunLedger
from orket.runtime.tool_scoreboard import build_tool_scoreboard, evaluate_promotion_gate

try:
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
except ModuleNotFoundError:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.rerun_diff_ledger import write_payload_with_diff_ledger


DEFAULT_OUT = PROJECT_ROOT / "benchmarks" / "results" / "tool_scoreboard.json"


def _events_path(root: Path, session_id: str) -> Path:
    return root / "runs" / str(session_id).strip() / "events.log"


def generate_scoreboard_payload(
    *,
    root: Path,
    session_id: str,
    scoreboard_policy_version: str,
    reliability_threshold: float,
    required_replay_runs: int,
    replay_pass_count: int,
    unresolved_drift_count: int,
) -> dict[str, Any]:
    events = AppendOnlyRunLedger(_events_path(root, session_id)).replay_events()
    scoreboard = build_tool_scoreboard(
        events,
        scoreboard_policy_version=scoreboard_policy_version,
    )
    promotion_gates = [
        evaluate_promotion_gate(
            tool_score=tool_row,
            reliability_threshold=reliability_threshold,
            required_replay_runs=required_replay_runs,
            replay_pass_count=replay_pass_count,
            unresolved_drift_count=unresolved_drift_count,
        )
        for tool_row in list(scoreboard.get("tools") or [])
        if isinstance(tool_row, dict)
    ]
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "session_id": str(session_id),
        "scoreboard": scoreboard,
        "promotion_gates": promotion_gates,
        "ok": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate ledger-only tool reliability scoreboard and promotion gates.")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--scoreboard-policy-version", default="1.0")
    parser.add_argument("--reliability-threshold", type=float, default=0.95)
    parser.add_argument("--required-replay-runs", type=int, default=3)
    parser.add_argument("--replay-pass-count", type=int, default=0)
    parser.add_argument("--unresolved-drift-count", type=int, default=0)
    args = parser.parse_args()

    root = args.root.resolve()
    session_id = str(args.session_id).strip()
    out_path = args.out.resolve()
    try:
        payload = generate_scoreboard_payload(
            root=root,
            session_id=session_id,
            scoreboard_policy_version=str(args.scoreboard_policy_version or "1.0"),
            reliability_threshold=float(args.reliability_threshold),
            required_replay_runs=int(args.required_replay_runs),
            replay_pass_count=int(args.replay_pass_count),
            unresolved_drift_count=int(args.unresolved_drift_count),
        )
    except (ValueError, TypeError, OSError) as exc:
        payload = {
            "generated_at": datetime.now(UTC).isoformat(),
            "session_id": session_id,
            "ok": False,
            "error": str(exc),
        }
        write_payload_with_diff_ledger(out_path, payload)
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=True))
        raise SystemExit(1) from exc

    write_payload_with_diff_ledger(out_path, payload)
    print(json.dumps({"status": "ok", "tools": len(payload["scoreboard"]["tools"])}, ensure_ascii=True))


if __name__ == "__main__":
    main()
