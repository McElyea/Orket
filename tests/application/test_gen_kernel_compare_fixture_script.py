from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_gen_kernel_compare_fixture_script(tmp_path: Path) -> None:
    out_path = tmp_path / "kernel_compare_fixture.json"
    result = subprocess.run(
        [sys.executable, "scripts/gen_kernel_compare_fixture.py", "--out", str(out_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert out_path.exists()

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["compare_mode"] == "structural_parity"
    assert payload["expect_outcome"] == "PASS"
    assert payload["run_a"]["contract_version"] == "kernel_api/v1"
    assert payload["run_b"]["contract_version"] == "kernel_api/v1"
