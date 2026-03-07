from __future__ import annotations

import json
import subprocess
from pathlib import Path


# Layer: contract
def test_ring_import_boundary_script_passes_on_repo(tmp_path: Path) -> None:
    out_path = tmp_path / "ring_import_boundary_check.json"
    result = subprocess.run(
        [
            "python",
            "scripts/governance/check_ring_import_boundaries.py",
            "--root",
            "orket",
            "--out",
            str(out_path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["violation_count"] == 0


# Layer: contract
def test_ring_import_boundary_script_detects_forbidden_import(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    compat_dir = root / "compatibility"
    compat_dir.mkdir(parents=True, exist_ok=True)
    (compat_dir / "demo.py").write_text(
        "import orket.runtime.execution_pipeline\n",
        encoding="utf-8",
    )
    out_path = tmp_path / "ring_import_boundary_check.json"
    result = subprocess.run(
        [
            "python",
            "scripts/governance/check_ring_import_boundaries.py",
            "--root",
            str(root),
            "--out",
            str(out_path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["ok"] is False
    assert payload["violation_count"] == 1
    first = payload["violations"][0]
    assert first["ring"] == "compatibility"
    assert first["imported_module"] == "orket.runtime.execution_pipeline"
