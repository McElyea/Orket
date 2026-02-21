from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _row(status: str, errors: list[str] | None = None) -> dict:
    payload = {
        "sidecar_parse_status": status,
        "sidecar_parse_errors": list(errors or []),
        "vram_total_mb": 1000.0,
        "vram_used_mb": 500.0,
        "ttft_ms": 10.0,
        "prefill_tps": 100.0,
        "decode_tps": 20.0,
        "thermal_start_c": 40.0,
        "thermal_end_c": 45.0,
        "kernel_launch_ms": 1.0,
        "model_load_ms": 10.0,
        "pcie_throughput_gbps": None,
        "cuda_graph_warmup_ms": None,
        "gpu_clock_mhz": None,
        "power_draw_watts": None,
        "fan_speed_percent": None,
    }
    return payload


def test_check_sidecar_parse_policy_passes_for_ok_payload(tmp_path: Path) -> None:
    summary = tmp_path / "summary.json"
    summary.write_text(
        json.dumps(
            {
                "sessions": [
                    {
                        "per_quant": [
                            {"quant_tag": "Q8_0", "hardware_sidecar": _row("OK")},
                        ]
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        ["python", "scripts/check_sidecar_parse_policy.py", "--summary", str(summary)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


def test_check_sidecar_parse_policy_fails_when_status_invalid(tmp_path: Path) -> None:
    summary = tmp_path / "summary.json"
    summary.write_text(
        json.dumps(
            {
                "sessions": [
                    {
                        "per_quant": [
                            {"quant_tag": "Q8_0", "hardware_sidecar": _row("BROKEN")},
                        ]
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "out.json"
    result = subprocess.run(
        [
            "python",
            "scripts/check_sidecar_parse_policy.py",
            "--summary",
            str(summary),
            "--out",
            str(out),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["status"] == "FAIL"
    assert any("invalid:sidecar_parse_status:BROKEN" in item for item in payload["failures"])

