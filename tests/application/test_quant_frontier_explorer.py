from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_quant_frontier_explorer_builds_artifact_and_appends_store(tmp_path: Path) -> None:
    summary = tmp_path / "sweep_summary.json"
    out = tmp_path / "frontier.json"
    storage = tmp_path / "frontiers"
    summary.write_text(
        json.dumps(
            {
                "generated_at": "2026-02-21T00:00:00Z",
                "commit_sha": "abc123",
                "hardware_fingerprint": "linux-6|cpu|8c|32gb|none",
                "execution_lane": "lab",
                "vram_profile": "safe",
                "sessions": [
                    {
                        "model_id": "qwen-coder",
                        "baseline_quant": "Q8_0",
                        "recommendation": "For this hardware, use Q6_K for best Vibe.",
                        "efficiency_frontier": {
                            "minimum_viable_quant_tag": "Q6_K",
                            "best_value_quant_tag": "Q8_0",
                        },
                        "per_quant": [
                            {
                                "quant_tag": "Q8_0",
                                "adherence_score": 1.0,
                                "total_latency": 3.0,
                                "peak_memory_rss": 3000.0,
                                "generation_tokens_per_second": 28.0,
                                "valid": True,
                            },
                            {
                                "quant_tag": "Q6_K",
                                "adherence_score": 0.98,
                                "total_latency": 2.8,
                                "peak_memory_rss": 2400.0,
                                "generation_tokens_per_second": 31.0,
                                "valid": True,
                            },
                        ],
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    first = subprocess.run(
        [
            "python",
            "scripts/quant_frontier_explorer.py",
            "--summary",
            str(summary),
            "--out",
            str(out),
            "--storage-root",
            str(storage),
            "--provenance-ref",
            "run-1:abc123",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert first.returncode == 0, first.stdout + "\n" + first.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["execution_lane"] == "lab"
    assert payload["vram_profile"] == "safe"
    assert payload["provenance"]["ref"] == "run-1:abc123"
    assert payload["sessions"][0]["minimum_viable_quant"] == "Q6_K"
    assert payload["sessions"][0]["best_value_quant"] == "Q8_0"

    second = subprocess.run(
        [
            "python",
            "scripts/quant_frontier_explorer.py",
            "--summary",
            str(summary),
            "--out",
            str(out),
            "--storage-root",
            str(storage),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert second.returncode == 0, second.stdout + "\n" + second.stderr
    store_path = next(storage.glob("*.json"))
    store_payload = json.loads(store_path.read_text(encoding="utf-8"))
    assert len(store_payload["history"]) == 2
