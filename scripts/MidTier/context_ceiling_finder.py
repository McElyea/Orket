from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build context ceiling recommendation artifact from context sweep summaries.")
    parser.add_argument("--contexts", required=True, help="Comma-separated context sizes, e.g. 4096,8192,16384")
    parser.add_argument("--summary-template", required=True, help="Summary path template containing {context}")
    parser.add_argument(
        "--run-template",
        default="",
        help="Optional command template to produce each summary. Placeholders: {context}, {summary_out}.",
    )
    parser.add_argument("--model-id", default="", help="Optional model id filter (defaults to first session).")
    parser.add_argument("--quant-tag", default="", help="Optional quant tag filter (defaults to frontier minimum/first row).")
    parser.add_argument("--adherence-min", type=float, default=0.0, help="Absolute minimum adherence score.")
    parser.add_argument("--ttft-ceiling-ms", type=float, default=0.0, help="If >0, ttft must be <= this value.")
    parser.add_argument("--decode-floor-tps", type=float, default=0.0, help="If >0, decode tps must be >= this value.")
    parser.add_argument("--include-invalid", action="store_true", help="Allow invalid rows in ceiling pass criteria.")
    parser.add_argument("--execution-lane", default="lab", choices=["ci", "lab"], help="Execution lane label.")
    parser.add_argument(
        "--vram-profile",
        default="safe",
        choices=["safe", "balanced", "stress"],
        help="VRAM safety profile label.",
    )
    parser.add_argument("--out", required=True, help="Output artifact path.")
    parser.add_argument("--provenance-ref", default="", help="Optional provenance reference (for example run_id:sha).")
    parser.add_argument(
        "--storage-root",
        default=".orket/durable/diagnostics/context_ceilings",
        help="Storage root for comparable context ceiling history.",
    )
    return parser.parse_args()


def _safe_token(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", str(value or "").strip()) or "unknown"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _row_is_valid(row: dict[str, Any]) -> bool:
    if "valid" in row:
        return bool(row.get("valid"))
    run_quality = str(row.get("run_quality_status") or "POLLUTED").strip().upper()
    token_status = str(row.get("token_metrics_status") or "TOKEN_AND_TIMING_UNAVAILABLE").strip().upper()
    return run_quality == "CLEAN" and token_status == "OK"


def _select_session(summary: dict[str, Any], model_id: str) -> dict[str, Any] | None:
    sessions = summary.get("sessions") if isinstance(summary.get("sessions"), list) else []
    if not sessions:
        return None
    if model_id:
        for session in sessions:
            if isinstance(session, dict) and str(session.get("model_id") or "") == model_id:
                return session
    for session in sessions:
        if isinstance(session, dict):
            return session
    return None


def _select_row(session: dict[str, Any], quant_tag: str) -> dict[str, Any] | None:
    per_quant = session.get("per_quant") if isinstance(session.get("per_quant"), list) else []
    rows = [row for row in per_quant if isinstance(row, dict)]
    if not rows:
        return None
    if quant_tag:
        for row in rows:
            if str(row.get("quant_tag") or "") == quant_tag:
                return row
    frontier = session.get("efficiency_frontier") if isinstance(session.get("efficiency_frontier"), dict) else {}
    minimum_viable = str(frontier.get("minimum_viable_quant_tag") or "")
    if minimum_viable:
        for row in rows:
            if str(row.get("quant_tag") or "") == minimum_viable:
                return row
    return sorted(rows, key=lambda row: int(row.get("quant_rank", 0) or 0), reverse=True)[0]


def _metric_decode_tps(row: dict[str, Any]) -> float | None:
    metric = row.get("generation_tokens_per_second")
    if isinstance(metric, (int, float)):
        return float(metric)
    sidecar = row.get("hardware_sidecar")
    if isinstance(sidecar, dict) and isinstance(sidecar.get("decode_tps"), (int, float)):
        return float(sidecar.get("decode_tps"))
    return None


def _metric_ttft_ms(row: dict[str, Any]) -> float | None:
    sidecar = row.get("hardware_sidecar")
    if isinstance(sidecar, dict) and isinstance(sidecar.get("ttft_ms"), (int, float)):
        return float(sidecar.get("ttft_ms"))
    return None


def _append_history(storage_root: Path, payload: dict[str, Any]) -> Path:
    key = "__".join(
        [
            _safe_token(str(payload.get("hardware_fingerprint") or "unknown")),
            _safe_token(str(payload.get("execution_lane") or "unknown")),
            _safe_token(str(payload.get("vram_profile") or "unknown")),
            _safe_token(str(payload.get("model_id") or "unknown")),
            _safe_token(str(payload.get("quant_tag") or "unknown")),
        ]
    )
    out_path = storage_root / f"{key}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    history: list[dict[str, Any]] = []
    if out_path.exists():
        existing = _load_json(out_path)
        if isinstance(existing.get("history"), list):
            history = [row for row in existing.get("history") if isinstance(row, dict)]
    history.append(payload)
    out_path.write_text(json.dumps({"history": history}, indent=2) + "\n", encoding="utf-8")
    return out_path


def main() -> int:
    args = _parse_args()
    contexts = [int(token.strip()) for token in str(args.contexts).split(",") if token.strip()]
    if not contexts:
        raise SystemExit("No contexts provided")
    contexts = sorted(set(contexts))

    points: list[dict[str, Any]] = []
    baseline_adherence: float | None = None
    hardware_fingerprint = "unknown"
    selected_model_id = str(args.model_id or "")
    selected_quant_tag = str(args.quant_tag or "")

    for context in contexts:
        summary_out = Path(str(args.summary_template).format(context=context))
        if str(args.run_template or "").strip():
            command = str(args.run_template).format(context=context, summary_out=str(summary_out).replace("\\", "/"))
            argv = shlex.split(command, posix=os.name != "nt")
            if not argv:
                raise SystemExit(f"context {context} run-template resolved to an empty command")
            result = subprocess.run(argv, shell=False, check=False, capture_output=True, text=True)
            if result.returncode != 0:
                raise SystemExit(
                    f"context {context} run-template failed with code {result.returncode}: {result.stdout}\n{result.stderr}"
                )
        summary = _load_json(summary_out)
        hardware_fingerprint = str(summary.get("hardware_fingerprint") or hardware_fingerprint)
        session = _select_session(summary, selected_model_id)
        if session is None:
            raise SystemExit(f"context {context}: no session available")
        if not selected_model_id:
            selected_model_id = str(session.get("model_id") or "unknown")
        row = _select_row(session, selected_quant_tag)
        if row is None:
            raise SystemExit(f"context {context}: no quant rows available")
        if not selected_quant_tag:
            selected_quant_tag = str(row.get("quant_tag") or "")

        adherence = float(row.get("adherence_score", 0.0) or 0.0)
        ttft_ms = _metric_ttft_ms(row)
        decode_tps = _metric_decode_tps(row)
        valid = _row_is_valid(row)
        if baseline_adherence is None:
            baseline_adherence = adherence
        degradation = round(max(0.0, (baseline_adherence or 0.0) - adherence), 6)
        reasons: list[str] = []
        if not args.include_invalid and not valid:
            reasons.append("INVALID_ROW")
        if adherence < float(args.adherence_min):
            reasons.append("ADHERENCE_BELOW_MIN")
        if float(args.ttft_ceiling_ms) > 0.0:
            if ttft_ms is None:
                reasons.append("TTFT_MISSING")
            elif ttft_ms > float(args.ttft_ceiling_ms):
                reasons.append("TTFT_ABOVE_CEILING")
        if float(args.decode_floor_tps) > 0.0:
            if decode_tps is None:
                reasons.append("DECODE_TPS_MISSING")
            elif decode_tps < float(args.decode_floor_tps):
                reasons.append("DECODE_TPS_BELOW_FLOOR")
        passed = len(reasons) == 0
        points.append(
            {
                "context": context,
                "adherence_score": adherence,
                "degradation_from_baseline": degradation,
                "ttft_ms": ttft_ms,
                "decode_tps": decode_tps,
                "valid": bool(valid),
                "passed": bool(passed),
                "reasons": reasons,
                "summary_path": str(summary_out).replace("\\", "/"),
            }
        )

    passing_contexts = [point["context"] for point in points if bool(point["passed"])]
    safe_context_ceiling = max(passing_contexts) if passing_contexts else None
    recommendation = (
        f"Recommended safe context ceiling: {safe_context_ceiling}."
        if safe_context_ceiling is not None
        else "No context window met the configured ceiling criteria."
    )

    artifact = {
        "schema_version": "explorer.context_ceiling.v1",
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "execution_lane": str(args.execution_lane),
        "vram_profile": str(args.vram_profile),
        "hardware_fingerprint": hardware_fingerprint,
        "model_id": selected_model_id or "unknown",
        "quant_tag": selected_quant_tag or "unknown",
        "provenance": {
            "ref": str(args.provenance_ref or ""),
            "summary_template": str(args.summary_template),
            "contexts": contexts,
        },
        "thresholds": {
            "adherence_min": float(args.adherence_min),
            "ttft_ceiling_ms": float(args.ttft_ceiling_ms),
            "decode_floor_tps": float(args.decode_floor_tps),
            "include_invalid": bool(args.include_invalid),
        },
        "safe_context_ceiling": safe_context_ceiling,
        "recommendation": recommendation,
        "points": points,
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")

    store_path = _append_history(Path(args.storage_root), artifact)
    print(
        json.dumps(
            {
                "status": "OK",
                "safe_context_ceiling": safe_context_ceiling,
                "out": str(out_path).replace("\\", "/"),
                "store": str(store_path).replace("\\", "/"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
