from __future__ import annotations

import argparse
import itertools
import json
import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


DEFAULT_ARCHITECTS = [
    "Command-R:35B",
    "qwen2.5:14b",
    "llama3.1:8b",
]

DEFAULT_AUDITORS = [
    "deepseek-r1:32b",
    "gemma3:27b",
]

DEFAULT_TESTS = [
    "tests/kernel/v1/test_odr_determinism_gate.py",
    "tests/kernel/v1/test_odr_refinement_behavior.py",
]


@dataclass(frozen=True)
class Pairing:
    architect: str
    auditor: str


def _parse_list(raw: str) -> List[str]:
    return [item.strip() for item in str(raw or "").split(",") if item.strip()]


def _parse_pytest_summary(text: str) -> Dict[str, int]:
    summary = {
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "skipped": 0,
        "xfailed": 0,
        "xpassed": 0,
    }
    for key in summary.keys():
        match = re.search(rf"(\d+)\s+{key}", text)
        if match is not None:
            summary[key] = int(match.group(1))
    return summary


def _score(summary: Dict[str, int], returncode: int) -> int:
    # Lower is better.
    score = 0
    score += summary.get("failed", 0) * 100
    score += summary.get("errors", 0) * 100
    score += summary.get("xpassed", 0) * 25
    score += summary.get("skipped", 0) * 2
    if returncode != 0:
        score += 500
    return score


def _run_pairing(
    pairing: Pairing,
    *,
    tests: List[str],
    nightly: bool,
    permutations: int,
    repeats: int,
    python_exe: str,
    workdir: Path,
) -> Dict[str, object]:
    env = dict(os.environ)
    env["ORKET_MODEL_ARCHITECT"] = pairing.architect
    env["ORKET_MODEL_INTEGRITY_GUARD"] = pairing.auditor
    env["ORKET_MODEL_REVIEWER"] = pairing.auditor
    if nightly:
        env["ODR_GATE_NIGHTLY"] = "1"
        env["ODR_PERMUTATIONS"] = str(permutations)
        env["ODR_REPEATS"] = str(repeats)
    else:
        env.pop("ODR_GATE_NIGHTLY", None)
        env.pop("ODR_PERMUTATIONS", None)
        env.pop("ODR_REPEATS", None)

    cmd = [python_exe, "-m", "pytest", "-q", *tests]
    started = time.monotonic()
    completed = subprocess.run(cmd, cwd=str(workdir), capture_output=True, text=True, env=env, check=False)
    elapsed_ms = int((time.monotonic() - started) * 1000)
    combined = f"{completed.stdout}\n{completed.stderr}".strip()
    summary = _parse_pytest_summary(combined)
    score = _score(summary, completed.returncode)
    hard_fail = completed.returncode != 0 or summary.get("failed", 0) > 0 or summary.get("errors", 0) > 0
    return {
        "architect_model": pairing.architect,
        "auditor_model": pairing.auditor,
        "returncode": int(completed.returncode),
        "elapsed_ms": elapsed_ms,
        "pytest_summary": summary,
        "hard_fail": hard_fail,
        "score": score,
        "stdout_tail": "\n".join((completed.stdout or "").strip().splitlines()[-8:]),
        "stderr_tail": "\n".join((completed.stderr or "").strip().splitlines()[-8:]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run architect/auditor model role matrix against ODR suites.")
    parser.add_argument(
        "--architect-models",
        default=",".join(DEFAULT_ARCHITECTS),
        help="Comma-separated architect model list.",
    )
    parser.add_argument(
        "--auditor-models",
        default=",".join(DEFAULT_AUDITORS),
        help="Comma-separated auditor model list.",
    )
    parser.add_argument(
        "--tests",
        default=",".join(DEFAULT_TESTS),
        help="Comma-separated pytest targets.",
    )
    parser.add_argument("--nightly", action="store_true", help="Enable nightly ODR gate tier env settings.")
    parser.add_argument("--permutations", type=int, default=50, help="ODR permutations when --nightly is set.")
    parser.add_argument("--repeats", type=int, default=20, help="ODR repeats when --nightly is set.")
    parser.add_argument("--python", default="python", help="Python executable.")
    parser.add_argument(
        "--out",
        default="benchmarks/results/odr_role_matrix.json",
        help="Output JSON path.",
    )
    args = parser.parse_args()

    architects = _parse_list(args.architect_models)
    auditors = _parse_list(args.auditor_models)
    tests = _parse_list(args.tests)
    if not architects:
        raise SystemExit("No architect models provided.")
    if not auditors:
        raise SystemExit("No auditor models provided.")
    if not tests:
        raise SystemExit("No tests provided.")

    workdir = Path.cwd()
    pairings = [Pairing(architect=a, auditor=b) for a, b in itertools.product(architects, auditors)]
    results: List[Dict[str, object]] = []
    for idx, pairing in enumerate(pairings, start=1):
        print(f"[{idx}/{len(pairings)}] architect={pairing.architect} auditor={pairing.auditor}")
        row = _run_pairing(
            pairing,
            tests=tests,
            nightly=bool(args.nightly),
            permutations=int(args.permutations),
            repeats=int(args.repeats),
            python_exe=str(args.python),
            workdir=workdir,
        )
        results.append(row)
        print(
            "  -> returncode={returncode} passed={passed} failed={failed} skipped={skipped} score={score}".format(
                returncode=row["returncode"],
                passed=row["pytest_summary"]["passed"],
                failed=row["pytest_summary"]["failed"],
                skipped=row["pytest_summary"]["skipped"],
                score=row["score"],
            )
        )

    ranked = sorted(results, key=lambda item: (bool(item["hard_fail"]), int(item["score"]), int(item["elapsed_ms"])))
    payload = {
        "matrix_v": "1.0.0",
        "tests": tests,
        "nightly": bool(args.nightly),
        "permutations": int(args.permutations) if args.nightly else None,
        "repeats": int(args.repeats) if args.nightly else None,
        "pairings_tested": len(results),
        "results": results,
        "ranking": ranked,
        "notes": [
            "Current ODR suites are deterministic fixture-based and model-role agnostic.",
            "Role model overrides are captured to support future model-in-the-loop suites.",
        ],
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {out_path}")
    if ranked:
        best = ranked[0]
        print(
            "Best pairing: architect={a} auditor={b} score={s} hard_fail={h}".format(
                a=best["architect_model"],
                b=best["auditor_model"],
                s=best["score"],
                h=best["hard_fail"],
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
