from __future__ import annotations

import subprocess
import sys
from pathlib import Path


SCRIPT = Path("scripts/sdk/check_sdk_tag_version.py").resolve()


def test_check_sdk_tag_version_accepts_matching_tag() -> None:
    """Layer: contract. Verifies SDK release tag gate accepts matching tag/version pairs."""
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--tag", "sdk-v0.1.0", "--repo-root", "."],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    assert "matches SDK version" in completed.stdout


def test_check_sdk_tag_version_rejects_mismatch() -> None:
    """Layer: contract. Verifies SDK release tag gate fails closed on tag/version drift."""
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--tag", "sdk-v9.9.9", "--repo-root", "."],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 1
    assert "E_SDK_TAG_VERSION_MISMATCH" in completed.stdout

