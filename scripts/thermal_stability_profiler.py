from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build thermal stability artifact from quant/context sweep summaries.")
    parser.add_argument("--summaries", required=True, help="Comma-separated summary paths in run order.")
    parser.add_argument("--model-id", default="", help="Optional model id filter.")
    parser.add_argument("--quant-tag", default="", help="Optional quant tag filter.")
    parser.add_argument("--cooldown-target-c", type=float, default=50.0)
    parser.add_argument("--polluted-thermal-threshold-c", type=float, default=85.0)
    parser.add_argument("--monotonic-window", type=int, default=3, help="Consecutive increases to flag heat soak.")
    parser.add_argument("--execution-lane", default="lab", choices=["ci", "lab"])
    parser.add_argument("--vram-profile", default="safe", choices=["safe", "balanced", "stress"])
    parser.add_argument("--provenance-ref", default="", help="Optional provenance reference (for example run_id:sha).")
    parser.add_argument("--out", required=True)
    parser.add_argument("--storage-root", default=".orket/durable/diagnostics/thermal_profiles")
    return parser.parse_args()


def _safe_token(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", str(value or "").strip()) or "unknown"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def _select_session(summary: dict[str, Any], model_id: str) -> dict[str, Any] | None:
    sessions = summary.get("sessions") if isinstance(summary.get("sessions"), list) else []
    if not sessions:
        return None
    if model_id:
        for session in sessions:
            if isinstance(session, dict) and str(session.get("model_id") or "") == model_id:
                return session
    return next((session for session in sessions if isinstance(session, dict)), None)


def _select_row(session: dict[str, Any], quant_tag: str) -> dict[str, Any] | None:
    rows = [row for row in (session.get("per_quant") or []) if isinstance(row, dict)]
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
    summary_paths = [Path(token.strip()) for token in str(args.summaries).split(",") if token.strip()]
    if not summary_paths:
        raise SystemExit("No summaries provided")

    model_id = str(args.model_id or "")
    quant_tag = str(args.quant_tag or "")
    points: list[dict[str, Any]] = []
    hardware_fingerprint = "unknown"
    monotonic_count = 0
    last_latency: float | None = None
    heat_soak_detected = False

    for idx, path in enumerate(summary_paths, start=1):
        summary = _load_json(path)
        hardware_fingerprint = str(summary.get("hardware_fingerprint") or hardware_fingerprint)
        session = _select_session(summary, model_id)
        if session is None:
            raise SystemExit(f"{path}: no session")
        if not model_id:
            model_id = str(session.get("model_id") or "unknown")
        row = _select_row(session, quant_tag)
        if row is None:
            raise SystemExit(f"{path}: no quant rows")
        if not quant_tag:
            quant_tag = str(row.get("quant_tag") or "unknown")
        sidecar = row.get("hardware_sidecar") if isinstance(row.get("hardware_sidecar"), dict) else {}
        thermal_start = sidecar.get("thermal_start_c")
        thermal_end = sidecar.get("thermal_end_c")
        total_latency = float(row.get("total_latency", 0.0) or 0.0)
        run_quality = str(row.get("run_quality_status") or "POLLUTED").strip().upper()
        thermal_delta = None
        if isinstance(thermal_start, (int, float)) and isinstance(thermal_end, (int, float)):
            thermal_delta = float(thermal_end) - float(thermal_start)

        polluted = False
        reasons: list[str] = []
        if isinstance(thermal_end, (int, float)) and float(thermal_end) > float(args.polluted_thermal_threshold_c):
            polluted = True
            reasons.append("THERMAL_END_ABOVE_THRESHOLD")
        if run_quality != "CLEAN":
            polluted = True
            reasons.append("RUN_QUALITY_NOT_CLEAN")

        if last_latency is not None and total_latency > last_latency:
            monotonic_count += 1
        else:
            monotonic_count = 0
        if monotonic_count >= max(1, int(args.monotonic_window)):
            heat_soak_detected = True
        last_latency = total_latency

        cooldown_ok = True
        if isinstance(thermal_start, (int, float)) and float(thermal_start) > float(args.cooldown_target_c):
            cooldown_ok = False
            reasons.append("COOLDOWN_TARGET_NOT_REACHED")

        points.append(
            {
                "run_index": idx,
                "summary_path": str(path).replace("\\", "/"),
                "total_latency": total_latency,
                "thermal_start_c": float(thermal_start) if isinstance(thermal_start, (int, float)) else None,
                "thermal_end_c": float(thermal_end) if isinstance(thermal_end, (int, float)) else None,
                "thermal_delta_c": thermal_delta,
                "polluted": polluted,
                "cooldown_ok": cooldown_ok,
                "reasons": sorted(set(reasons)),
            }
        )

    polluted_rate = round(
        sum(1 for point in points if bool(point["polluted"])) / len(points),
        6,
    )
    cooldown_fail_rate = round(
        sum(1 for point in points if not bool(point["cooldown_ok"])) / len(points),
        6,
    )
    recommendation = "Thermal profile stable."
    if heat_soak_detected:
        recommendation = "Heat-soak trend detected; increase cooldown between runs."
    elif polluted_rate > 0:
        recommendation = "Thermal pollution detected; reduce load or increase cooldown."

    artifact = {
        "schema_version": "explorer.thermal_stability.v1",
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "execution_lane": str(args.execution_lane),
        "vram_profile": str(args.vram_profile),
        "hardware_fingerprint": hardware_fingerprint,
        "model_id": model_id or "unknown",
        "quant_tag": quant_tag or "unknown",
        "provenance": {
            "ref": str(args.provenance_ref or ""),
            "summary_paths": [str(path).replace("\\", "/") for path in summary_paths],
        },
        "thresholds": {
            "cooldown_target_c": float(args.cooldown_target_c),
            "polluted_thermal_threshold_c": float(args.polluted_thermal_threshold_c),
            "monotonic_window": int(args.monotonic_window),
        },
        "heat_soak_detected": bool(heat_soak_detected),
        "polluted_run_rate": polluted_rate,
        "cooldown_failure_rate": cooldown_fail_rate,
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
                "heat_soak_detected": bool(heat_soak_detected),
                "out": str(out_path).replace("\\", "/"),
                "store": str(store_path).replace("\\", "/"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
