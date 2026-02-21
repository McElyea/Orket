from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_explorer_schema_contracts_pass_for_valid_payloads(tmp_path: Path) -> None:
    frontier = tmp_path / "frontier.json"
    context = tmp_path / "context.json"
    thermal = tmp_path / "thermal.json"
    frontier.write_text(
        json.dumps(
            {
                "generated_at": "2026-02-21T00:00:00Z",
                "execution_lane": "lab",
                "vram_profile": "safe",
                "hardware_fingerprint": "hw",
                "model_id": "m",
                "quant_tag": "q",
                "sessions": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    context.write_text(
        json.dumps(
            {
                "generated_at": "2026-02-21T00:00:00Z",
                "execution_lane": "lab",
                "vram_profile": "safe",
                "hardware_fingerprint": "hw",
                "model_id": "m",
                "quant_tag": "q",
                "safe_context_ceiling": 8192,
                "points": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    thermal.write_text(
        json.dumps(
            {
                "generated_at": "2026-02-21T00:00:00Z",
                "execution_lane": "lab",
                "vram_profile": "safe",
                "hardware_fingerprint": "hw",
                "model_id": "m",
                "quant_tag": "q",
                "heat_soak_detected": False,
                "points": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            "python",
            "scripts/check_explorer_schema_contracts.py",
            "--frontier",
            str(frontier),
            "--context",
            str(context),
            "--thermal",
            str(thermal),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "PASS"


def test_explorer_schema_contracts_fail_on_missing_required(tmp_path: Path) -> None:
    frontier = tmp_path / "frontier.json"
    frontier.write_text(json.dumps({"generated_at": "x"}) + "\n", encoding="utf-8")
    result = subprocess.run(
        [
            "python",
            "scripts/check_explorer_schema_contracts.py",
            "--frontier",
            str(frontier),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["status"] == "FAIL"
    assert any("frontier:missing:execution_lane" == item for item in payload["failures"])
