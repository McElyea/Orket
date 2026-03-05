from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


DEFAULT_TESTS = [
    "tests/test_runtime_nudge_no_repeat.py",
    "tests/test_runtime_disambiguation_flow.py",
    "tests/test_runtime_nudge_witness_chain.py",
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run TextMystery policy conformance tests (hint/disambiguation gates).")
    parser.add_argument("--textmystery-root", default="C:/Source/Orket-Extensions/TextMystery")
    parser.add_argument("--output", default="")
    parser.add_argument("--test", action="append", default=[], help="Optional explicit test path(s), repeatable.")
    return parser.parse_args()


def _run_pytest(textmystery_root: Path, tests: list[str]) -> dict[str, Any]:
    command = [sys.executable, "-m", "pytest", "-q", *tests]
    started = time.perf_counter()
    proc = subprocess.run(
        command,
        cwd=textmystery_root,
        capture_output=True,
        text=True,
        check=False,
    )
    duration_ms = round((time.perf_counter() - started) * 1000.0, 3)
    return {
        "command": command,
        "returncode": int(proc.returncode),
        "duration_ms": duration_ms,
        "stdout": str(proc.stdout or ""),
        "stderr": str(proc.stderr or ""),
    }


def main() -> int:
    args = _parse_args()
    textmystery_root = Path(args.textmystery_root).resolve()
    tests = list(args.test) if args.test else list(DEFAULT_TESTS)
    if not textmystery_root.exists():
        raise FileNotFoundError(f"textmystery root not found: {textmystery_root}")

    run = _run_pytest(textmystery_root=textmystery_root, tests=tests)
    payload = {
        "schema_version": "textmystery_policy_conformance.v1",
        "generated_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "textmystery_root": str(textmystery_root),
        "tests": tests,
        "status": "pass" if run["returncode"] == 0 else "fail",
        "run": run,
    }

    output = str(args.output or "").strip()
    if output:
        out_path = Path(output).resolve()
    else:
        out_path = Path.cwd() / "workspace" / "diagnostics" / "textmystery_policy_conformance.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if run["returncode"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
