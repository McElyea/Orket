from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _summary(context: int, *, valid: bool, adherence: float, ttft_ms: float, decode_tps: float) -> dict:
    return {
        "generated_at": "2026-02-21T00:00:00Z",
        "hardware_fingerprint": "linux-6|cpu|8c|32gb|none",
        "execution_lane": "lab",
        "vram_profile": "safe",
        "sessions": [
            {
                "model_id": "qwen-coder",
                "efficiency_frontier": {
                    "minimum_viable_quant_tag": "Q6_K",
                    "best_value_quant_tag": "Q8_0",
                },
                "per_quant": [
                    {
                        "quant_tag": "Q6_K",
                        "quant_rank": 600,
                        "adherence_score": adherence,
                        "run_quality_status": "CLEAN" if valid else "POLLUTED",
                        "token_metrics_status": "OK",
                        "generation_tokens_per_second": decode_tps,
                        "valid": valid,
                        "hardware_sidecar": {"ttft_ms": ttft_ms, "decode_tps": decode_tps},
                    }
                ],
            }
        ],
        "_context": context,
    }


def test_context_ceiling_finder_emits_safe_ceiling_and_degradation(tmp_path: Path) -> None:
    summaries = tmp_path / "summaries"
    summaries.mkdir(parents=True, exist_ok=True)
    (summaries / "c4096.json").write_text(
        json.dumps(_summary(4096, valid=True, adherence=0.99, ttft_ms=100, decode_tps=30), indent=2) + "\n",
        encoding="utf-8",
    )
    (summaries / "c8192.json").write_text(
        json.dumps(_summary(8192, valid=True, adherence=0.96, ttft_ms=150, decode_tps=26), indent=2) + "\n",
        encoding="utf-8",
    )
    (summaries / "c16384.json").write_text(
        json.dumps(_summary(16384, valid=False, adherence=0.91, ttft_ms=260, decode_tps=20), indent=2) + "\n",
        encoding="utf-8",
    )

    out = tmp_path / "context_ceiling.json"
    store = tmp_path / "store"
    result = subprocess.run(
        [
            "python",
            "scripts/context_ceiling_finder.py",
            "--contexts",
            "4096,8192,16384",
            "--summary-template",
            str(summaries / "c{context}.json"),
            "--adherence-min",
            "0.95",
            "--ttft-ceiling-ms",
            "200",
            "--decode-floor-tps",
            "24",
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
    assert payload["safe_context_ceiling"] == 8192
    assert payload["execution_lane"] == "lab"
    assert payload["vram_profile"] == "safe"
    points = {row["context"]: row for row in payload["points"]}
    assert points[4096]["degradation_from_baseline"] == 0.0
    assert points[8192]["degradation_from_baseline"] == 0.03
    assert points[16384]["passed"] is False
    assert "INVALID_ROW" in points[16384]["reasons"]

    store_files = list(store.glob("*.json"))
    assert len(store_files) == 1
    store_payload = json.loads(store_files[0].read_text(encoding="utf-8"))
    assert len(store_payload["history"]) == 1
