from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List


HARDENING_TEST_TARGETS: List[str] = [
    "tests/adapters/test_gitea_state_adapter.py",
    "tests/adapters/test_gitea_state_adapter_contention.py",
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate gitea state backend hardening gate using contention/failure-injection test targets."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Run hardening test targets with pytest and record real exit codes.",
    )
    parser.add_argument(
        "--out",
        default="benchmarks/results/gitea_state_hardening_check.json",
        help="Output JSON artifact path.",
    )
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Exit non-zero when hardening gate is not ready.",
    )
    return parser.parse_args()


def evaluate_hardening(exits: Dict[str, int]) -> Dict[str, object]:
    failures: List[str] = []
    for target, code in exits.items():
        if int(code) != 0:
            failures.append(f"{target} exit_code={code}")
    return {
        "ready": len(failures) == 0,
        "targets": exits,
        "failures": failures,
    }


def _run_target(target: str) -> int:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", target, "-q"],
        check=False,
    )
    return int(proc.returncode)


def main() -> int:
    args = _parse_args()
    if args.execute:
        exits = {target: _run_target(target) for target in HARDENING_TEST_TARGETS}
    else:
        exits = {target: 0 for target in HARDENING_TEST_TARGETS}

    result = evaluate_hardening(exits)
    result["executed"] = bool(args.execute)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    if bool(args.require_ready) and not bool(result.get("ready")):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
