#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.proof.trusted_terraform_plan_decision_contract import (
    DEFAULT_LIVE_RUN_OUTPUT,
    DEFAULT_SCENARIO,
    DEFAULT_WORKSPACE_ROOT,
    relative_to_repo,
)
from scripts.proof.trusted_terraform_plan_decision_workflow import SCENARIOS, execute_trusted_terraform_plan_decision, persist_live_run


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Trusted Terraform Plan Decision proof slice.")
    parser.add_argument("--workspace-root", default=str(DEFAULT_WORKSPACE_ROOT), help="Workspace root for the proof run.")
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), default=DEFAULT_SCENARIO, help="Proof scenario to execute.")
    parser.add_argument("--run-index", type=int, default=1, help="Stable run index used in generated proof ids.")
    parser.add_argument("--output", default=str(DEFAULT_LIVE_RUN_OUTPUT), help="Stable live proof output path.")
    parser.add_argument("--json", action="store_true", help="Print the persisted live proof JSON.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    payload = execute_trusted_terraform_plan_decision(
        workspace_root=Path(str(args.workspace_root)),
        scenario=str(args.scenario),
        run_index=int(args.run_index),
    )
    output = Path(str(args.output)).resolve()
    persisted = persist_live_run(output, payload)
    if args.json:
        print(json.dumps(persisted, indent=2, ensure_ascii=True))
    else:
        print(
            " ".join(
                [
                    f"observed_result={persisted.get('observed_result')}",
                    f"workflow_result={persisted.get('workflow_result')}",
                    f"scenario={persisted.get('scenario')}",
                    f"output={relative_to_repo(output)}",
                ]
            )
        )
    return 0 if persisted.get("observed_result") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
