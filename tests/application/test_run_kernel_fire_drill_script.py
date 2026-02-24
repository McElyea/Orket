from __future__ import annotations

import subprocess
import sys


def test_run_kernel_fire_drill_script_returns_zero() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/run_kernel_fire_drill.py"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
