from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_analyze_vram_fragmentation_emits_expected_report(tmp_path: Path) -> None:
    summary = tmp_path / "summary.json"
    summary.write_text(
        json.dumps(
            {
                "sessions": [
                    {
                        "model_id": "qwen-coder",
                        "per_quant": [
                            {"hardware_sidecar": {"vram_total_mb": 24000, "vram_used_mb": 12000}},
                            {"hardware_sidecar": {"vram_total_mb": 24000, "vram_used_mb": 19200}},
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "frag.json"
    result = subprocess.run(
        [
            "python",
            "scripts/analyze_vram_fragmentation.py",
            "--summary",
            str(summary),
            "--out",
            str(out),
            "--high-risk-threshold",
            "0.2",
            "--medium-risk-threshold",
            "0.1",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "vram.fragmentation.v1"
    model = payload["models"][0]
    assert model["model_id"] == "qwen-coder"
    assert model["sample_count"] == 2
    assert model["fragmentation_score"] == 0.3
    assert model["risk"] == "HIGH"


def test_analyze_vram_fragmentation_handles_missing_sidecar_samples(tmp_path: Path) -> None:
    summary = tmp_path / "summary.json"
    summary.write_text(
        json.dumps({"sessions": [{"model_id": "qwen-coder", "per_quant": [{}]}]}),
        encoding="utf-8",
    )
    out = tmp_path / "frag.json"
    result = subprocess.run(
        [
            "python",
            "scripts/analyze_vram_fragmentation.py",
            "--summary",
            str(summary),
            "--out",
            str(out),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    model = payload["models"][0]
    assert model["sample_count"] == 0
    assert model["risk"] == "UNKNOWN"
    assert model["reason"] == "no_sidecar_vram_samples"

