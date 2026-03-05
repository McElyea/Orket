from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List


PHASE3_TEST_TARGETS: List[str] = [
    "tests/adapters/test_gitea_state_adapter.py",
    "tests/adapters/test_gitea_state_adapter_contention.py",
    "tests/adapters/test_gitea_state_multi_runner_simulation.py",
    "tests/application/test_gitea_state_worker.py",
    "tests/application/test_gitea_state_worker_coordinator.py",
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate phase-3 readiness for gitea state backend multi-runner rollout."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Run phase-3 test targets with pytest and capture exit codes.",
    )
    parser.add_argument(
        "--pilot-readiness",
        default="benchmarks/results/gitea_state_pilot_readiness.json",
        help="Pilot readiness artifact path.",
    )
    parser.add_argument(
        "--hardening-readiness",
        default="benchmarks/results/gitea_state_hardening_check.json",
        help="Hardening readiness artifact path.",
    )
    parser.add_argument(
        "--out",
        default="benchmarks/results/gitea_state_phase3_readiness.json",
        help="Output JSON artifact path.",
    )
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Exit non-zero when readiness is false.",
    )
    return parser.parse_args()


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _run_target(target: str) -> int:
    proc = subprocess.run([sys.executable, "-m", "pytest", target, "-q"], check=False)
    return int(proc.returncode)


def evaluate_phase3_readiness(
    *,
    pilot_ready: bool,
    hardening_ready: bool,
    test_exits: Dict[str, int],
) -> Dict[str, Any]:
    failures: List[str] = []
    if not pilot_ready:
        failures.append("pilot readiness gate is not ready")
    if not hardening_ready:
        failures.append("hardening readiness gate is not ready")
    for target, code in test_exits.items():
        if int(code) != 0:
            failures.append(f"{target} exit_code={code}")
    return {
        "ready": len(failures) == 0,
        "pilot_ready": bool(pilot_ready),
        "hardening_ready": bool(hardening_ready),
        "phase3_test_targets": test_exits,
        "failures": failures,
    }


def main() -> int:
    args = _parse_args()
    pilot_payload = _read_json(Path(args.pilot_readiness))
    hardening_payload = _read_json(Path(args.hardening_readiness))
    pilot_ready = bool(pilot_payload.get("ready"))
    hardening_ready = bool(hardening_payload.get("ready"))
    if args.execute:
        exits = {target: _run_target(target) for target in PHASE3_TEST_TARGETS}
    else:
        exits = {target: 0 for target in PHASE3_TEST_TARGETS}
    result = evaluate_phase3_readiness(
        pilot_ready=pilot_ready,
        hardening_ready=hardening_ready,
        test_exits=exits,
    )
    result["executed"] = bool(args.execute)
    result["pilot_readiness_path"] = str(args.pilot_readiness)
    result["hardening_readiness_path"] = str(args.hardening_readiness)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    if bool(args.require_ready) and not bool(result.get("ready")):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
