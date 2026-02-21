from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _summary_payload() -> dict:
    return {
        "generated_at": "2026-02-21T00:00:00Z",
        "execution_lane": "lab",
        "vram_profile": "safe",
        "hardware_fingerprint": "linux-6|cpu|8c|32gb|none",
        "sessions": [
            {
                "model_id": "qwen-coder",
                "recommendation": "For this hardware, use Q6_K for best Vibe.",
                "efficiency_frontier": {
                    "minimum_viable_quant_tag": "Q6_K",
                    "best_value_quant_tag": "Q8_0",
                },
                "per_quant": [
                    {
                        "quant_tag": "Q8_0",
                        "quant_rank": 800,
                        "adherence_score": 1.0,
                        "total_latency": 3.2,
                        "generation_tokens_per_second": 28.7,
                        "run_quality_status": "CLEAN",
                        "token_metrics_status": "OK",
                        "hardware_sidecar": {"sidecar_parse_status": "OK"},
                    },
                    {
                        "quant_tag": "Q6_K",
                        "quant_rank": 600,
                        "adherence_score": 0.98,
                        "total_latency": 2.8,
                        "generation_tokens_per_second": 31.0,
                        "run_quality_status": "CLEAN",
                        "token_metrics_status": "OK",
                        "hardware_sidecar": {"sidecar_parse_status": "OPTIONAL_FIELD_MISSING"},
                    },
                    {
                        "quant_tag": "Q4_K_M",
                        "quant_rank": 400,
                        "adherence_score": 0.7,
                        "total_latency": 2.0,
                        "generation_tokens_per_second": 35.0,
                        "run_quality_status": "POLLUTED",
                        "token_metrics_status": "OK",
                        "hardware_sidecar": {"sidecar_parse_status": "REQUIRED_FIELD_MISSING"},
                    },
                ],
            }
        ],
    }


def test_render_quant_sweep_report_excludes_invalid_by_default(tmp_path: Path) -> None:
    summary = tmp_path / "sweep_summary.json"
    out_md = tmp_path / "sweep_report.md"
    out_scatter = tmp_path / "sweep_scatter.json"
    summary.write_text(json.dumps(_summary_payload(), indent=2) + "\n", encoding="utf-8")

    result = subprocess.run(
        [
            "python",
            "scripts/render_quant_sweep_report.py",
            "--summary",
            str(summary),
            "--out-md",
            str(out_md),
            "--out-scatter",
            str(out_scatter),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    scatter_payload = json.loads(out_scatter.read_text(encoding="utf-8"))
    assert scatter_payload["execution_lane"] == "lab"
    assert scatter_payload["vram_profile"] == "safe"
    assert len(scatter_payload["points"]) == 2
    roles = {point["quant_tag"]: point["frontier_role"] for point in scatter_payload["points"]}
    assert roles["Q6_K"] == "minimum_viable"
    assert roles["Q8_0"] == "best_value"

    md_text = out_md.read_text(encoding="utf-8")
    assert "execution_lane: `lab`" in md_text
    assert "vram_profile: `safe`" in md_text
    assert "Q4_K_M" not in md_text


def test_render_quant_sweep_report_can_include_invalid(tmp_path: Path) -> None:
    summary = tmp_path / "sweep_summary.json"
    out_md = tmp_path / "sweep_report.md"
    out_scatter = tmp_path / "sweep_scatter.json"
    summary.write_text(json.dumps(_summary_payload(), indent=2) + "\n", encoding="utf-8")

    result = subprocess.run(
        [
            "python",
            "scripts/render_quant_sweep_report.py",
            "--summary",
            str(summary),
            "--out-md",
            str(out_md),
            "--out-scatter",
            str(out_scatter),
            "--include-invalid",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    scatter_payload = json.loads(out_scatter.read_text(encoding="utf-8"))
    assert scatter_payload["include_invalid"] is True
    assert len(scatter_payload["points"]) == 3
    quants = {point["quant_tag"] for point in scatter_payload["points"]}
    assert "Q4_K_M" in quants
