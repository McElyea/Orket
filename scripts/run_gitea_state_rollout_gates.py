from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run gitea state rollout gates (pilot, hardening, phase3) and emit a bundle summary."
    )
    parser.add_argument(
        "--out",
        default="benchmarks/results/gitea_state_rollout_gates.json",
        help="Output summary artifact path.",
    )
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Exit non-zero if any gate is not ready.",
    )
    return parser.parse_args()


def run_gate(command: List[str]) -> Dict[str, Any]:
    proc = subprocess.run(command, check=False)
    return {
        "command": command,
        "exit_code": int(proc.returncode),
        "ok": int(proc.returncode) == 0,
    }


def evaluate_gate_bundle(results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    failures = [name for name, result in results.items() if not bool(result.get("ok"))]
    return {
        "ready": len(failures) == 0,
        "results": results,
        "failures": failures,
    }


def main() -> int:
    args = _parse_args()

    pilot_cmd = [
        sys.executable,
        "scripts/check_gitea_state_pilot_readiness.py",
        "--out",
        "benchmarks/results/gitea_state_pilot_readiness.json",
        "--require-ready",
    ]
    hardening_cmd = [
        sys.executable,
        "scripts/check_gitea_state_hardening.py",
        "--execute",
        "--out",
        "benchmarks/results/gitea_state_hardening_check.json",
        "--require-ready",
    ]
    phase3_cmd = [
        sys.executable,
        "scripts/check_gitea_state_phase3_readiness.py",
        "--execute",
        "--pilot-readiness",
        "benchmarks/results/gitea_state_pilot_readiness.json",
        "--hardening-readiness",
        "benchmarks/results/gitea_state_hardening_check.json",
        "--out",
        "benchmarks/results/gitea_state_phase3_readiness.json",
        "--require-ready",
    ]

    results = {
        "pilot_readiness": run_gate(pilot_cmd),
        "hardening": run_gate(hardening_cmd),
        "phase3": run_gate(phase3_cmd),
    }
    summary = evaluate_gate_bundle(results)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))

    if bool(args.require_ready) and not bool(summary.get("ready")):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
