from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.common.rerun_diff_ledger import _payload_digest
from scripts.odr.context_continuity_lane import load_lane_config, resolve_lane_artifact_path


def _load_compare_payload(compare_payload_path: Path) -> dict[str, Any]:
    payload = json.loads(compare_payload_path.read_text(encoding="utf-8"))
    budget_verdicts = list(payload.get("budget_verdicts") or [])
    if not budget_verdicts:
        raise ValueError("Compare payload must declare budget_verdicts.")
    return payload


def build_context_continuity_verdict_payload_from_payload(
    compare_payload: dict[str, Any],
    *,
    config_path: Path | None = None,
) -> dict[str, Any]:
    config = load_lane_config(config_path)
    compare_digest_payload = {
        key: value for key, value in compare_payload.items() if key != "compare_payload_path"
    }
    compare_thresholds = dict((compare_payload.get("lane_config_snapshot") or {}).get("decision_thresholds") or {})
    config_thresholds = dict(config.get("decision_thresholds") or {})
    if compare_thresholds != config_thresholds:
        raise ValueError("Compare payload decision thresholds do not match the locked lane config.")

    budget_verdicts = [dict(row) for row in list(compare_payload.get("budget_verdicts") or [])]
    continuity_modes = sorted({str(row["continuity_mode"]) for row in budget_verdicts})
    summary_by_mode: dict[str, Any] = {}
    for continuity_mode in continuity_modes:
        rows = [row for row in budget_verdicts if str(row["continuity_mode"]) == continuity_mode]
        worthwhile_budgets = sorted(
            int(row["locked_budget"]) for row in rows if str(row["verdict"]).startswith("worthwhile_at_")
        )
        quality_only_budgets = sorted(
            int(row["locked_budget"]) for row in rows if str(row["verdict"]) == "continuity_quality_success_only"
        )
        non_worthwhile_budgets = sorted(
            int(row["locked_budget"]) for row in rows if str(row["verdict"]) == "not_materially_worthwhile"
        )
        global_verdict = None
        if len(worthwhile_budgets) == len(config["locked_budgets"]) and len(rows) == len(config["locked_budgets"]):
            global_verdict = "worthwhile_at_both_locked_budgets"
        elif (
            len(quality_only_budgets) == len(config["locked_budgets"])
            and len(rows) == len(config["locked_budgets"])
            and not worthwhile_budgets
        ):
            global_verdict = "continuity_quality_success_only"
        summary_by_mode[continuity_mode] = {
            "global_verdict": global_verdict,
            "worthwhile_budgets": worthwhile_budgets,
            "continuity_quality_success_only_budgets": quality_only_budgets,
            "non_worthwhile_budgets": non_worthwhile_budgets,
            "verdicts_by_budget": {
                str(int(row["locked_budget"])): str(row["verdict"])
                for row in sorted(rows, key=lambda row: int(row["locked_budget"]))
            },
        }

    return {
        "schema_version": "odr.context_continuity.verdict.v2",
        "generated_at": datetime.now(UTC).isoformat(),
        "ended_at": datetime.now(UTC).isoformat(),
        "lane_config_snapshot": {
            "config_path": str(config["config_path"]),
            "requirements_authority": str(config["requirements_authority"]),
            "implementation_authority": str(config["implementation_authority"]),
            "decision_thresholds": config_thresholds,
        },
        "source_compare_artifact": {
            "path": str(compare_payload.get("compare_payload_path") or ""),
            "artifact_sha256": _payload_digest(compare_digest_payload),
            "schema_version": str(compare_payload.get("schema_version") or ""),
        },
        "pair_scope": str(config["pair_scope"]),
        "evidence_scope": str(compare_payload.get("evidence_scope") or ""),
        "continuity_modes": continuity_modes,
        "budget_verdicts": budget_verdicts,
        "summary": {"by_mode": summary_by_mode},
    }


def build_context_continuity_verdict_payload(
    compare_payload_path: Path,
    *,
    config_path: Path | None = None,
) -> dict[str, Any]:
    compare_payload = _load_compare_payload(compare_payload_path)
    compare_payload["compare_payload_path"] = str(compare_payload_path)
    return build_context_continuity_verdict_payload_from_payload(compare_payload, config_path=config_path)


def resolve_default_verdict_output_path(config_path: Path | None = None) -> Path:
    config = load_lane_config(config_path)
    return resolve_lane_artifact_path(config, "verdict_output")
