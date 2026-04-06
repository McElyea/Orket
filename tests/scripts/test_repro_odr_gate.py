# LIFECYCLE: live
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.contract


def test_repro_odr_gate_expected_hash_mismatch_reports_root_only() -> None:
    script = Path("tools/repro_odr_gate.py")
    fixture = Path("tests/kernel/v1/vectors/odr/odr_torture_pack.json")

    proc = subprocess.run(
        [
            sys.executable,
            str(script),
            "--seed",
            "1729",
            "--fixture",
            str(fixture),
            "--perm-index",
            "0",
            "--rounds",
            "0",
            "--mode",
            "pr",
            "--expected-hash",
            "0" * 64,
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 1
    assert "failure_reason=CANON_MISMATCH" in proc.stdout
    assert "first_diff_path=$" in proc.stdout
