from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from orket.application.services.microservices_acceptance_reports import normalize_microservices_unlock_report

try:
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.rerun_diff_ledger import write_payload_with_diff_ledger


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Decide whether microservices pilot mode should be enabled from unlock-check output."
    )
    parser.add_argument(
        "--unlock-report",
        default="benchmarks/results/acceptance/microservices_unlock_check.json",
        help="Path to check_microservices_unlock output JSON.",
    )
    parser.add_argument(
        "--out",
        default="benchmarks/results/acceptance/microservices_pilot_decision.json",
        help="Output decision JSON path.",
    )
    parser.add_argument(
        "--env-out",
        default="",
        help="Optional .env-style output path with ORKET_ENABLE_MICROSERVICES=<true|false>.",
    )
    parser.add_argument(
        "--require-enabled",
        action="store_true",
        help="Exit non-zero if decision is to keep microservices disabled.",
    )
    return parser.parse_args()


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"Unlock report not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Unlock report is not valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"Unlock report must be a JSON object: {path}")
    return payload


def _normalize_unlock_report(payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = normalize_microservices_unlock_report(payload)
    return {"valid": bool(normalized), **normalized}


def decide_from_unlock_report(payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized_report = _normalize_unlock_report(payload)
    if not bool(normalized_report.get("valid")):
        unlocked = False
        normalized_failures = ["unlock report missing or invalid"]
        recommended_default_builder_variant = None
    else:
        unlocked = bool(normalized_report.get("unlocked"))
        normalized_failures = list(normalized_report.get("failures", []))
        recommended_default_builder_variant = normalized_report.get("recommended_default_builder_variant")
    decision = {
        "enable_microservices": unlocked,
        "recommended_env": {
            "ORKET_ENABLE_MICROSERVICES": "true" if unlocked else "false",
        },
        "decision_reason": (
            "unlock criteria satisfied"
            if unlocked
            else "unlock criteria not satisfied; keep microservices locked"
        ),
        "unlock_failures": normalized_failures,
        "recommended_default_builder_variant": recommended_default_builder_variant,
    }
    return decision


def main() -> int:
    args = _parse_args()
    report = _load_json(Path(args.unlock_report))
    decision = decide_from_unlock_report(report)
    rendered = json.dumps(decision, indent=2)
    print(rendered)

    out_path = Path(args.out)
    write_payload_with_diff_ledger(out_path, decision)

    env_out = str(args.env_out or "").strip()
    if env_out:
        env_path = Path(env_out)
        env_path.parent.mkdir(parents=True, exist_ok=True)
        env_path.write_text(
            f"ORKET_ENABLE_MICROSERVICES={decision['recommended_env']['ORKET_ENABLE_MICROSERVICES']}\n",
            encoding="utf-8",
        )

    if bool(args.require_enabled) and not bool(decision.get("enable_microservices")):
        raise SystemExit(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
