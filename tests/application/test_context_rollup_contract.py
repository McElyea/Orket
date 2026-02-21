from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _ceiling() -> dict:
    return {
        "safe_context_ceiling": 8192,
        "points": [
            {"context": 4096, "passed": True},
            {"context": 8192, "passed": True},
            {"context": 16384, "passed": False},
        ],
    }


def _rollup(valid: bool = True) -> dict:
    payload = {
        "schema_version": "explorer.context_sweep_rollup.v1",
        "execution_lane": "lab",
        "vram_profile": "safe",
        "provenance": {"ref": "r1"},
        "safe_context_ceiling": 8192,
        "contexts_total": 3,
        "contexts_passed": 2,
        "contexts_failed": 1,
    }
    if not valid:
        payload["contexts_failed"] = 2
    return payload


def test_context_rollup_contract_passes(tmp_path: Path) -> None:
    rollup = tmp_path / "rollup.json"
    ceiling = tmp_path / "ceiling.json"
    rollup.write_text(json.dumps(_rollup(), indent=2) + "\n", encoding="utf-8")
    ceiling.write_text(json.dumps(_ceiling(), indent=2) + "\n", encoding="utf-8")
    result = subprocess.run(
        [
            "python",
            "scripts/check_context_rollup_contract.py",
            "--rollup",
            str(rollup),
            "--context-ceiling",
            str(ceiling),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


def test_context_rollup_contract_fails_on_mismatch(tmp_path: Path) -> None:
    rollup = tmp_path / "rollup.json"
    ceiling = tmp_path / "ceiling.json"
    rollup.write_text(json.dumps(_rollup(valid=False), indent=2) + "\n", encoding="utf-8")
    ceiling.write_text(json.dumps(_ceiling(), indent=2) + "\n", encoding="utf-8")
    result = subprocess.run(
        [
            "python",
            "scripts/check_context_rollup_contract.py",
            "--rollup",
            str(rollup),
            "--context-ceiling",
            str(ceiling),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["status"] == "FAIL"
