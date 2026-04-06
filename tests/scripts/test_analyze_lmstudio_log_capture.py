# LIFECYCLE: live
from __future__ import annotations

import json
from pathlib import Path

from scripts.protocol.analyze_lmstudio_log_capture import main


def _capture_payload() -> str:
    return """2026-03-05 10:00:00 [DEBUG]
LlamaV4::predict slot selection: session_id=<empty> server-selected (LCP/LRU)
slot update_slots: id 3 | task 4 | failed to truncate tokens with position >= 13 - clearing the memory
slot update_slots: id 3 | task 4 | forcing full prompt re-processing due to lack of cache data (likely due to SWA or hybrid/recurrent memory)
slot update_slots: id 3 | task 4 | cache reuse is not supported - ignoring n_cache_reuse = 256
prompt eval time =      33.24 ms /    51 tokens (    0.65 ms per token,  1534.25 tokens per second)
       eval time =     475.33 ms /    29 tokens (   16.39 ms per token,    61.01 tokens per second)
Received request: POST to /v1/chat/completions with body  {
  "model": "qwen3.5-4b",
  "max_tokens": 512,
  "stream": false
}
      "finish_reason": "stop"
-----
Review 1 of the Data:
The model can follow strict output contracts.
"""


def test_analyze_lmstudio_log_capture_splits_and_extracts_metrics(tmp_path: Path) -> None:
    input_path = tmp_path / "capture.txt"
    out_root = tmp_path / "out"
    input_path.write_text(_capture_payload(), encoding="utf-8")

    exit_code = main(["--input", str(input_path), "--out-root", str(out_root), "--strict"])
    assert exit_code == 0

    raw_log = out_root / "raw" / "lmstudio_server.log"
    commentary = out_root / "raw" / "critic_commentary.txt"
    metrics_path = out_root / "analysis" / "lmstudio_cache_metrics.json"
    manifest_path = out_root / "analysis" / "lmstudio_capture_manifest.json"

    assert raw_log.exists()
    assert commentary.exists()
    assert metrics_path.exists()
    assert manifest_path.exists()

    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert metrics["schema_version"] == "lmstudio_cache_metrics.v1"
    assert metrics["raw_line_count"] > 0
    assert metrics["commentary_line_count"] > 0
    assert metrics["metrics"]["counts"]["session_id_empty"] == 1
    assert metrics["metrics"]["counts"]["forcing_full_prompt_reprocess"] == 1
    assert metrics["metrics"]["counts"]["failed_truncate_clearing_memory"] == 1
    assert metrics["metrics"]["finish_reason_counts"]["stop"] == 1
    assert metrics["metrics"]["max_tokens_histogram"]["512"] == 1
    assert int(metrics["metrics"]["prompt_eval_tps"]["count"]) == 1
    assert int(metrics["metrics"]["generation_eval_tps"]["count"]) == 1
    assert int(metrics["metrics"]["generation_eval_tps_filtered"]["count"]) == 1

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "lmstudio_capture_manifest.v1"
    assert manifest["raw_line_count"] == metrics["raw_line_count"]
    assert manifest["commentary_line_count"] == metrics["commentary_line_count"]


def test_analyze_lmstudio_log_capture_strict_fails_when_no_raw_lines(tmp_path: Path) -> None:
    input_path = tmp_path / "capture.txt"
    out_root = tmp_path / "out"
    input_path.write_text("Review 2:\nOnly commentary\n", encoding="utf-8")

    exit_code = main(["--input", str(input_path), "--out-root", str(out_root), "--strict"])
    assert exit_code == 1
