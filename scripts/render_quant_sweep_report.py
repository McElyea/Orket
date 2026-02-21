from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


VALID_SIDECAR_STATUSES = {"OK", "OPTIONAL_FIELD_MISSING", "NOT_APPLICABLE"}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render quant sweep operator report artifacts.")
    parser.add_argument("--summary", required=True, help="Path to sweep_summary.json")
    parser.add_argument("--out-md", required=True, help="Output markdown report path")
    parser.add_argument("--out-scatter", required=True, help="Output scatter dataset json path")
    parser.add_argument(
        "--include-invalid",
        action="store_true",
        help="Include invalid rows in scatter/report tables (KPI policy is unchanged).",
    )
    return parser.parse_args()


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def _is_valid_row(row: dict[str, Any]) -> bool:
    run_quality_status = str(row.get("run_quality_status") or "POLLUTED").strip().upper()
    if run_quality_status != "CLEAN":
        return False
    token_status = str(row.get("token_metrics_status") or "TOKEN_AND_TIMING_UNAVAILABLE").strip().upper()
    if token_status != "OK":
        return False
    sidecar = row.get("hardware_sidecar")
    if isinstance(sidecar, dict):
        parse_status = str(sidecar.get("sidecar_parse_status") or "NOT_APPLICABLE").strip().upper()
        if parse_status not in VALID_SIDECAR_STATUSES:
            return False
    return True


def _render_markdown(
    *,
    summary: dict[str, Any],
    points: list[dict[str, Any]],
    out_scatter_path: Path,
    include_invalid: bool,
) -> str:
    matrix = summary.get("matrix") if isinstance(summary.get("matrix"), dict) else {}
    execution_lane = str(summary.get("execution_lane") or matrix.get("execution_lane") or "unknown")
    vram_profile = str(summary.get("vram_profile") or matrix.get("vram_profile") or "unknown")
    hardware_fingerprint = str(summary.get("hardware_fingerprint") or "unknown")
    generated_at = str(summary.get("generated_at") or "unknown")
    lines = [
        "# Quant Sweep Report",
        "",
        f"- generated_at: `{generated_at}`",
        f"- execution_lane: `{execution_lane}`",
        f"- vram_profile: `{vram_profile}`",
        f"- hardware_fingerprint: `{hardware_fingerprint}`",
        f"- include_invalid: `{str(bool(include_invalid)).lower()}`",
        f"- scatter_dataset: `{str(out_scatter_path).replace(chr(92), '/')}`",
        "",
        "## Session Summary",
    ]

    sessions = summary.get("sessions") if isinstance(summary.get("sessions"), list) else []
    for session in sessions:
        if not isinstance(session, dict):
            continue
        model_id = str(session.get("model_id") or "unknown")
        frontier = session.get("efficiency_frontier") if isinstance(session.get("efficiency_frontier"), dict) else {}
        lines.extend(
            [
                f"- model: `{model_id}`",
                f"  - minimum_viable_quant: `{str(frontier.get('minimum_viable_quant_tag') or 'none')}`",
                f"  - best_value_quant: `{str(frontier.get('best_value_quant_tag') or 'none')}`",
                f"  - recommendation: `{str(session.get('recommendation') or '')}`",
            ]
        )

    lines.extend(
        [
            "",
            "## TPS vs Adherence Data",
            "",
            "| model_id | quant_tag | generation_tps | adherence_score | valid | frontier_role |",
            "| --- | --- | ---: | ---: | --- | --- |",
        ]
    )
    for point in sorted(points, key=lambda item: (item["model_id"], item["quant_rank"]), reverse=True):
        lines.append(
            "| {model_id} | {quant_tag} | {generation_tps} | {adherence_score} | {valid} | {frontier_role} |".format(
                model_id=point["model_id"],
                quant_tag=point["quant_tag"],
                generation_tps="null" if point["generation_tps"] is None else f"{point['generation_tps']:.3f}",
                adherence_score=f"{point['adherence_score']:.3f}",
                valid=str(bool(point["valid"])).lower(),
                frontier_role=point["frontier_role"] or "",
            )
        )
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = _parse_args()
    summary_path = Path(args.summary)
    out_md = Path(args.out_md)
    out_scatter = Path(args.out_scatter)

    summary = _load_json(summary_path)
    sessions = summary.get("sessions") if isinstance(summary.get("sessions"), list) else []

    points: list[dict[str, Any]] = []
    for session in sessions:
        if not isinstance(session, dict):
            continue
        model_id = str(session.get("model_id") or "unknown")
        frontier = session.get("efficiency_frontier") if isinstance(session.get("efficiency_frontier"), dict) else {}
        min_viable = str(frontier.get("minimum_viable_quant_tag") or "")
        best_value = str(frontier.get("best_value_quant_tag") or "")
        per_quant = session.get("per_quant") if isinstance(session.get("per_quant"), list) else []
        for row in per_quant:
            if not isinstance(row, dict):
                continue
            valid = _is_valid_row(row)
            if not bool(args.include_invalid) and not valid:
                continue
            quant_tag = str(row.get("quant_tag") or "unknown")
            frontier_role = ""
            if quant_tag and quant_tag == min_viable:
                frontier_role = "minimum_viable"
            if quant_tag and quant_tag == best_value:
                frontier_role = "best_value" if not frontier_role else "minimum_viable+best_value"
            generation_tps = row.get("generation_tokens_per_second")
            if not isinstance(generation_tps, (int, float)):
                sidecar = row.get("hardware_sidecar")
                if isinstance(sidecar, dict):
                    generation_tps = sidecar.get("decode_tps")
            points.append(
                {
                    "model_id": model_id,
                    "quant_tag": quant_tag,
                    "quant_rank": int(row.get("quant_rank", 0) or 0),
                    "generation_tps": float(generation_tps) if isinstance(generation_tps, (int, float)) else None,
                    "adherence_score": float(row.get("adherence_score", 0.0) or 0.0),
                    "total_latency": float(row.get("total_latency", 0.0) or 0.0),
                    "valid": bool(valid),
                    "frontier_role": frontier_role,
                }
            )

    matrix = summary.get("matrix") if isinstance(summary.get("matrix"), dict) else {}
    scatter_payload = {
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "source_summary": str(summary_path).replace("\\", "/"),
        "execution_lane": str(summary.get("execution_lane") or matrix.get("execution_lane") or "unknown"),
        "vram_profile": str(summary.get("vram_profile") or matrix.get("vram_profile") or "unknown"),
        "include_invalid": bool(args.include_invalid),
        "points": points,
    }

    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_scatter.parent.mkdir(parents=True, exist_ok=True)
    out_scatter.write_text(json.dumps(scatter_payload, indent=2) + "\n", encoding="utf-8")
    out_md.write_text(
        _render_markdown(
            summary=summary,
            points=points,
            out_scatter_path=out_scatter,
            include_invalid=bool(args.include_invalid),
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "OK",
                "summary": str(summary_path).replace("\\", "/"),
                "out_md": str(out_md).replace("\\", "/"),
                "out_scatter": str(out_scatter).replace("\\", "/"),
                "points": len(points),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
