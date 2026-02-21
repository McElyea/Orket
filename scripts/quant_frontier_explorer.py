from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build quant frontier explorer artifact from sweep summary.")
    parser.add_argument("--summary", required=True, help="Path to sweep_summary.json")
    parser.add_argument("--out", required=True, help="Path for frontier explorer artifact")
    parser.add_argument("--provenance-ref", default="", help="Optional provenance reference (for example run_id:sha).")
    parser.add_argument(
        "--storage-root",
        default=".orket/durable/diagnostics/frontiers",
        help="Storage root for comparable historical frontier records",
    )
    return parser.parse_args()


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def _safe_token(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", str(value or "").strip()) or "unknown"


def _build_session_rows(summary: dict[str, Any]) -> list[dict[str, Any]]:
    sessions = summary.get("sessions") if isinstance(summary.get("sessions"), list) else []
    rows: list[dict[str, Any]] = []
    for session in sessions:
        if not isinstance(session, dict):
            continue
        model_id = str(session.get("model_id") or "unknown")
        frontier = session.get("efficiency_frontier") if isinstance(session.get("efficiency_frontier"), dict) else {}
        per_quant = session.get("per_quant") if isinstance(session.get("per_quant"), list) else []
        rows.append(
            {
                "model_id": model_id,
                "baseline_quant": str(session.get("baseline_quant") or ""),
                "minimum_viable_quant": str(frontier.get("minimum_viable_quant_tag") or ""),
                "best_value_quant": str(frontier.get("best_value_quant_tag") or ""),
                "recommendation": str(session.get("recommendation") or ""),
                "quant_rows": [
                    {
                        "quant_tag": str(row.get("quant_tag") or ""),
                        "adherence_score": float(row.get("adherence_score", 0.0) or 0.0),
                        "total_latency": float(row.get("total_latency", 0.0) or 0.0),
                        "peak_memory_rss": float(row.get("peak_memory_rss", 0.0) or 0.0),
                        "generation_tokens_per_second": (
                            float(row.get("generation_tokens_per_second"))
                            if isinstance(row.get("generation_tokens_per_second"), (int, float))
                            else None
                        ),
                        "valid": bool(row.get("valid", False)),
                    }
                    for row in per_quant
                    if isinstance(row, dict)
                ],
            }
        )
    return rows


def _append_store(payload: dict[str, Any], storage_root: Path) -> Path:
    hardware_fingerprint = str(payload.get("hardware_fingerprint") or "unknown")
    execution_lane = str(payload.get("execution_lane") or "unknown")
    vram_profile = str(payload.get("vram_profile") or "unknown")
    store_name = f"{_safe_token(hardware_fingerprint)}__{_safe_token(execution_lane)}__{_safe_token(vram_profile)}.json"
    store_path = storage_root / store_name
    store_path.parent.mkdir(parents=True, exist_ok=True)
    existing_history: list[dict[str, Any]] = []
    if store_path.exists():
        existing = _load_json(store_path)
        history = existing.get("history")
        if isinstance(history, list):
            existing_history = [row for row in history if isinstance(row, dict)]
    existing_history.append(payload)
    store_path.write_text(json.dumps({"history": existing_history}, indent=2) + "\n", encoding="utf-8")
    return store_path


def main() -> int:
    args = _parse_args()
    summary_path = Path(args.summary)
    out_path = Path(args.out)
    summary = _load_json(summary_path)
    payload = {
        "schema_version": "explorer.frontier.v1",
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "source_summary": str(summary_path).replace("\\", "/"),
        "summary_generated_at": str(summary.get("generated_at") or ""),
        "commit_sha": str(summary.get("commit_sha") or ""),
        "hardware_fingerprint": str(summary.get("hardware_fingerprint") or "unknown"),
        "execution_lane": str(summary.get("execution_lane") or (summary.get("matrix") or {}).get("execution_lane") or "unknown"),
        "vram_profile": str(summary.get("vram_profile") or (summary.get("matrix") or {}).get("vram_profile") or "unknown"),
        "provenance": {
            "ref": str(args.provenance_ref or ""),
            "source_summary": str(summary_path).replace("\\", "/"),
            "commit_sha": str(summary.get("commit_sha") or ""),
        },
        "sessions": _build_session_rows(summary),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    store_path = _append_store(payload, Path(args.storage_root))
    print(
        json.dumps(
            {
                "status": "OK",
                "out": str(out_path).replace("\\", "/"),
                "store": str(store_path).replace("\\", "/"),
                "sessions": len(payload["sessions"]),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
