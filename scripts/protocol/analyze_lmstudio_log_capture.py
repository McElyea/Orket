from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path
import re
import statistics
import sys
from typing import Any

try:
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.rerun_diff_ledger import write_payload_with_diff_ledger


_PROMPT_EVAL_RE = re.compile(
    r"prompt eval time\s*=\s*([0-9.]+) ms /\s*([0-9]+) tokens .*?([0-9.]+) tokens per second"
)
_EVAL_RE = re.compile(
    r"(?<!prompt )eval time\s*=\s*([0-9.]+) ms /\s*([0-9]+) tokens .*?([0-9.]+) tokens per second"
)
_MAX_TOKENS_RE = re.compile(r'"max_tokens"\s*:\s*([0-9]+)')
_FINISH_REASON_RE = re.compile(r'"finish_reason"\s*:\s*"([^"]+)"')


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze LM Studio log captures for cache/state metrics.")
    parser.add_argument(
        "--input",
        default="docs/internal/LMStudioData.txt",
        help="Input LM Studio capture path.",
    )
    parser.add_argument(
        "--out-root",
        default="benchmarks/results/protocol/local_prompting/lmstudio_cache_study/baseline",
        help="Output root for raw split and analysis artifacts.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when no raw runtime log lines can be identified.",
    )
    return parser


def _iso_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _is_commentary_start(line: str) -> bool:
    token = str(line or "").strip()
    if not token:
        return False
    lowered = token.lower()
    markers = (
        "review 1 of the data:",
        "review 2:",
        "gemini said",
    )
    return any(lowered.startswith(marker) for marker in markers)


def _find_commentary_start(lines: list[str]) -> int:
    for index, line in enumerate(lines):
        if _is_commentary_start(line):
            return index
    return -1


def _quantile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    rank = max(0.0, min(1.0, float(q))) * float(len(sorted_values) - 1)
    lower = int(rank)
    upper = min(len(sorted_values) - 1, lower + 1)
    frac = rank - float(lower)
    return float(sorted_values[lower] * (1.0 - frac) + sorted_values[upper] * frac)


def _metric_summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "count": 0,
            "min": 0.0,
            "max": 0.0,
            "median": 0.0,
            "p90": 0.0,
            "p95": 0.0,
            "mean": 0.0,
        }
    ordered = sorted(float(value) for value in values)
    return {
        "count": len(ordered),
        "min": round(ordered[0], 6),
        "max": round(ordered[-1], 6),
        "median": round(float(statistics.median(ordered)), 6),
        "p90": round(_quantile(ordered, 0.90), 6),
        "p95": round(_quantile(ordered, 0.95), 6),
        "mean": round(float(statistics.fmean(ordered)), 6),
    }


def _histogram(values: list[int]) -> dict[str, int]:
    bins: dict[str, int] = {}
    for value in values:
        key = str(int(value))
        bins[key] = bins.get(key, 0) + 1
    return {key: bins[key] for key in sorted(bins, key=lambda token: int(token))}


def _extract_metrics(raw_lines: list[str]) -> dict[str, Any]:
    prompt_eval_ms: list[float] = []
    prompt_eval_tps: list[float] = []
    eval_ms: list[float] = []
    eval_tps: list[float] = []
    eval_ms_filtered: list[float] = []
    eval_tps_filtered: list[float] = []
    max_tokens: list[int] = []
    finish_reasons: dict[str, int] = {}

    for line in raw_lines:
        prompt_match = _PROMPT_EVAL_RE.search(line)
        if prompt_match:
            prompt_eval_ms.append(float(prompt_match.group(1)))
            prompt_eval_tps.append(float(prompt_match.group(3)))

        eval_match = _EVAL_RE.search(line)
        if eval_match:
            eval_ms_value = float(eval_match.group(1))
            eval_tokens_value = int(eval_match.group(2))
            eval_tps_value = float(eval_match.group(3))
            eval_ms.append(eval_ms_value)
            eval_tps.append(eval_tps_value)
            if eval_tokens_value >= 20 and eval_tps_value < 10000.0:
                eval_ms_filtered.append(eval_ms_value)
                eval_tps_filtered.append(eval_tps_value)

        max_tokens_match = _MAX_TOKENS_RE.search(line)
        if max_tokens_match:
            max_tokens.append(int(max_tokens_match.group(1)))

        finish_match = _FINISH_REASON_RE.search(line)
        if finish_match:
            key = str(finish_match.group(1)).strip().lower()
            finish_reasons[key] = finish_reasons.get(key, 0) + 1

    counts = {
        "session_id_empty": sum(1 for line in raw_lines if "session_id=<empty>" in line),
        "forcing_full_prompt_reprocess": sum(
            1 for line in raw_lines if "forcing full prompt re-processing due to lack of cache data" in line
        ),
        "failed_truncate_clearing_memory": sum(
            1 for line in raw_lines if "failed to truncate tokens with position >=" in line
        ),
        "cache_reuse_ignored": sum(
            1 for line in raw_lines if "cache reuse is not supported - ignoring n_cache_reuse" in line
        ),
        "client_disconnected": sum(1 for line in raw_lines if "Client disconnected. Stopping generation" in line),
        "operation_canceled": sum(1 for line in raw_lines if "Operation canceled" in line),
    }

    return {
        "counts": counts,
        "finish_reason_counts": {key: finish_reasons[key] for key in sorted(finish_reasons)},
        "max_tokens_histogram": _histogram(max_tokens),
        "prompt_eval_ms": _metric_summary(prompt_eval_ms),
        "prompt_eval_tps": _metric_summary(prompt_eval_tps),
        "generation_eval_ms": _metric_summary(eval_ms),
        "generation_eval_tps": _metric_summary(eval_tps),
        "generation_eval_ms_filtered": _metric_summary(eval_ms_filtered),
        "generation_eval_tps_filtered": _metric_summary(eval_tps_filtered),
    }


def _write_text(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(lines).rstrip("\n")
    if payload:
        payload += "\n"
    path.write_text(payload, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    input_path = Path(str(args.input)).resolve()
    out_root = Path(str(args.out_root)).resolve()
    raw_root = out_root / "raw"
    analysis_root = out_root / "analysis"

    lines = input_path.read_text(encoding="utf-8", errors="replace").splitlines()
    commentary_start = _find_commentary_start(lines)
    if commentary_start < 0:
        raw_lines = list(lines)
        commentary_lines: list[str] = []
    else:
        raw_lines = list(lines[:commentary_start])
        commentary_lines = list(lines[commentary_start:])

    raw_log_path = raw_root / "lmstudio_server.log"
    commentary_path = raw_root / "critic_commentary.txt"
    _write_text(raw_log_path, raw_lines)
    _write_text(commentary_path, commentary_lines)

    metrics = _extract_metrics(raw_lines)
    metrics_payload = {
        "schema_version": "lmstudio_cache_metrics.v1",
        "generated_at_utc": _iso_now(),
        "input_path": str(input_path).replace("\\", "/"),
        "raw_log_path": str(raw_log_path).replace("\\", "/"),
        "commentary_path": str(commentary_path).replace("\\", "/"),
        "raw_line_count": len(raw_lines),
        "commentary_line_count": len(commentary_lines),
        "commentary_start_line": int(commentary_start + 1) if commentary_start >= 0 else 0,
        "metrics": metrics,
    }
    metrics_path = analysis_root / "lmstudio_cache_metrics.json"
    write_payload_with_diff_ledger(metrics_path, metrics_payload)

    manifest_payload = {
        "schema_version": "lmstudio_capture_manifest.v1",
        "generated_at_utc": _iso_now(),
        "input_path": str(input_path).replace("\\", "/"),
        "raw_log_path": str(raw_log_path).replace("\\", "/"),
        "commentary_path": str(commentary_path).replace("\\", "/"),
        "metrics_path": str(metrics_path).replace("\\", "/"),
        "raw_line_count": len(raw_lines),
        "commentary_line_count": len(commentary_lines),
        "commentary_start_line": int(commentary_start + 1) if commentary_start >= 0 else 0,
    }
    write_payload_with_diff_ledger(analysis_root / "lmstudio_capture_manifest.json", manifest_payload)

    if bool(args.strict) and len(raw_lines) == 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
