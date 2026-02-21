from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _summary(*, latency: float, thermal_start: float, thermal_end: float, clean: bool) -> dict:
    return {
        "generated_at": "2026-02-21T00:00:00Z",
        "hardware_fingerprint": "linux-6|cpu|8c|32gb|none",
        "sessions": [
            {
                "model_id": "qwen-coder",
                "efficiency_frontier": {"minimum_viable_quant_tag": "Q6_K"},
                "per_quant": [
                    {
                        "quant_tag": "Q6_K",
                        "quant_rank": 600,
                        "total_latency": latency,
                        "run_quality_status": "CLEAN" if clean else "POLLUTED",
                        "hardware_sidecar": {
                            "thermal_start_c": thermal_start,
                            "thermal_end_c": thermal_end,
                        },
                    }
                ],
            }
        ],
    }


def test_thermal_stability_profiler_flags_heat_soak_and_pollution(tmp_path: Path) -> None:
    s1 = tmp_path / "s1.json"
    s2 = tmp_path / "s2.json"
    s3 = tmp_path / "s3.json"
    s1.write_text(json.dumps(_summary(latency=1.0, thermal_start=48, thermal_end=70, clean=True), indent=2) + "\n", encoding="utf-8")
    s2.write_text(json.dumps(_summary(latency=1.2, thermal_start=52, thermal_end=78, clean=True), indent=2) + "\n", encoding="utf-8")
    s3.write_text(json.dumps(_summary(latency=1.4, thermal_start=56, thermal_end=88, clean=False), indent=2) + "\n", encoding="utf-8")

    out = tmp_path / "thermal_profile.json"
    store = tmp_path / "store"
    result = subprocess.run(
        [
            "python",
            "scripts/thermal_stability_profiler.py",
            "--summaries",
            f"{s1},{s2},{s3}",
            "--cooldown-target-c",
            "50",
            "--polluted-thermal-threshold-c",
            "85",
            "--monotonic-window",
            "2",
            "--out",
            str(out),
            "--storage-root",
            str(store),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["heat_soak_detected"] is True
    assert payload["polluted_run_rate"] > 0
    assert payload["cooldown_failure_rate"] > 0
    assert "Heat-soak trend detected" in payload["recommendation"]
    assert len(payload["points"]) == 3

    store_files = list(store.glob("*.json"))
    assert len(store_files) == 1
