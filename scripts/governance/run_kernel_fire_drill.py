#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys


def main() -> int:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "tests/kernel/v1/test_registry.py",
        "tests/kernel/v1/test_validator_schema_contract.py",
        "tests/interfaces/test_api_kernel_lifecycle.py",
    ]
    completed = subprocess.run(cmd, check=False)
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
