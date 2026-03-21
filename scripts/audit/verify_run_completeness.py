#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.audit.audit_support import evaluate_run_completeness, now_utc_iso, write_report

DEFAULT_OUTPUT = "benchmarks/results/audit/verify_run_completeness.json"


def build_report(*, workspace: Path, session_id: str) -> dict[str, object]:
    evaluation = evaluate_run_completeness(workspace=workspace, session_id=session_id)
    observed_result = "success" if bool(evaluation["mar_complete"]) else "failure"
    return {
        "schema_version": "audit.verify_run_completeness.v1",
        "recorded_at_utc": now_utc_iso(),
        "proof_kind": "structural",
        "observed_path": "primary",
        "observed_result": observed_result,
        **evaluation,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate whether one completed run satisfies MAR v1 completeness.")
    parser.add_argument("--workspace", required=True, help="Workspace root containing runs/<session_id>/run_summary.json.")
    parser.add_argument("--session-id", required=True, help="Run/session id to evaluate.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Stable rerunnable JSON output path.")
    parser.add_argument("--json", action="store_true", help="Print the persisted JSON payload.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    output_path = Path(str(args.output)).resolve()
    payload = build_report(workspace=Path(str(args.workspace)).resolve(), session_id=str(args.session_id))
    persisted = write_report(output_path, payload)
    if args.json:
        print(json.dumps({**persisted, "output_path": str(output_path)}, indent=2, ensure_ascii=True))
    else:
        print(
            " ".join(
                [
                    f"mar_complete={persisted.get('mar_complete')}",
                    f"replay_ready={persisted.get('replay_ready')}",
                    f"stability_status={persisted.get('stability_status')}",
                    f"output={output_path}",
                ]
            )
        )
    return 0 if bool(persisted.get("mar_complete")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
