from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from orket.application.services.gitea_state_pilot import (
    collect_gitea_state_pilot_inputs,
    evaluate_gitea_state_pilot_readiness,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check whether gitea state backend pilot prerequisites are satisfied."
    )
    parser.add_argument(
        "--out",
        default="benchmarks/results/gitea_state_pilot_readiness.json",
        help="Output JSON artifact path.",
    )
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Exit non-zero when readiness checks fail.",
    )
    return parser.parse_args()


def collect_runtime_inputs() -> Dict[str, Any]:
    return collect_gitea_state_pilot_inputs()


def evaluate_readiness(inputs: Dict[str, Any]) -> Dict[str, Any]:
    return evaluate_gitea_state_pilot_readiness(inputs)


def main() -> int:
    args = _parse_args()
    inputs = collect_runtime_inputs()
    result = evaluate_readiness(inputs)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    if bool(args.require_ready) and not bool(result.get("ready")):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
