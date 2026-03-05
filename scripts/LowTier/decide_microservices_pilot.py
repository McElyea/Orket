from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Decide whether microservices pilot mode should be enabled from unlock-check output."
    )
    parser.add_argument(
        "--unlock-report",
        default="benchmarks/results/microservices_unlock_check.json",
        help="Path to check_microservices_unlock output JSON.",
    )
    parser.add_argument(
        "--out",
        default="benchmarks/results/microservices_pilot_decision.json",
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


def decide_from_unlock_report(payload: Dict[str, Any]) -> Dict[str, Any]:
    unlocked = bool(payload.get("unlocked"))
    failures = payload.get("failures", [])
    if not isinstance(failures, list):
        failures = []
    normalized_failures: List[str] = [str(item) for item in failures]
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
        "recommended_default_builder_variant": payload.get("recommended_default_builder_variant"),
    }
    return decision


def main() -> int:
    args = _parse_args()
    report = _load_json(Path(args.unlock_report))
    decision = decide_from_unlock_report(report)
    rendered = json.dumps(decision, indent=2)
    print(rendered)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(rendered, encoding="utf-8")

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
