from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _run(command: list[str]) -> None:
    print(f"+ {' '.join(command)}")
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> None:
    _run([sys.executable, "scripts/check_dependency_direction.py"])
    _run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/platform/test_architecture_volatility_boundaries.py",
            "tests/platform/test_no_old_namespaces.py",
            "-q",
        ]
    )


if __name__ == "__main__":
    main()
