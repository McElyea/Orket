from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run security regression suite and emit status artifact.")
    parser.add_argument(
        "--pytest-targets",
        nargs="*",
        default=[
            "tests/runtime/test_extension_components.py",
            "tests/runtime/test_extension_manager.py",
            "tests/interfaces/test_api.py",
        ],
    )
    parser.add_argument("--out-json", default="benchmarks/results/security/security_regression_status.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cmd = ["python", "-m", "pytest", *list(args.pytest_targets), "-q"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    payload = {
        "ok": result.returncode == 0,
        "command": cmd,
        "returncode": result.returncode,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "stdout_tail": "\n".join(result.stdout.strip().splitlines()[-20:]),
        "stderr_tail": "\n".join(result.stderr.strip().splitlines()[-20:]),
    }
    out = Path(args.out_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
