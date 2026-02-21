from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _summary(*, thermal_start: float | None, vram_total: float | None, vram_used: float | None, parse_status: str = "OK") -> dict:
    sidecar = {"sidecar_parse_status": parse_status}
    if thermal_start is not None:
        sidecar["thermal_start_c"] = thermal_start
    if vram_total is not None:
        sidecar["vram_total_mb"] = vram_total
    if vram_used is not None:
        sidecar["vram_used_mb"] = vram_used
    return {
        "sessions": [
            {
                "model_id": "qwen-coder",
                "per_quant": [
                    {
                        "quant_tag": "Q6_K",
                        "hardware_sidecar": sidecar,
                    }
                ],
            }
        ]
    }


def test_lab_guard_checker_fails_on_cooldown_or_vram_limit(tmp_path: Path) -> None:
    summary = tmp_path / "summary.json"
    summary.write_text(
        json.dumps(_summary(thermal_start=60, vram_total=100, vram_used=90), indent=2) + "\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            "python",
            "scripts/check_lab_guards.py",
            "--summary",
            str(summary),
            "--cooldown-target-c",
            "50",
            "--vram-profile",
            "safe",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["status"] == "FAIL"
    assert "COOLDOWN_TARGET_NOT_MET" in payload["polluted_status_reasons"]
    assert "VRAM_RATIO_EXCEEDED" in payload["polluted_status_reasons"]


def test_lab_guard_checker_skips_when_metrics_not_applicable(tmp_path: Path) -> None:
    summary = tmp_path / "summary.json"
    summary.write_text(
        json.dumps(_summary(thermal_start=None, vram_total=None, vram_used=None, parse_status="NOT_APPLICABLE"), indent=2) + "\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            "python",
            "scripts/check_lab_guards.py",
            "--summary",
            str(summary),
            "--allow-skip",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "SKIP"
    assert payload["skip_reasons"]
    assert payload["polluted_status_reasons"] == []


def test_lab_guard_checker_passes_within_limits(tmp_path: Path) -> None:
    summary = tmp_path / "summary.json"
    summary.write_text(
        json.dumps(_summary(thermal_start=45, vram_total=100, vram_used=40), indent=2) + "\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            "python",
            "scripts/check_lab_guards.py",
            "--summary",
            str(summary),
            "--cooldown-target-c",
            "50",
            "--vram-profile",
            "safe",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "PASS"
    assert payload["polluted_status_reasons"] == []
