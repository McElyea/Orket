from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List


REQUIRED_CONFIG_KEYS = [
    "gitea_url",
    "gitea_token",
    "gitea_owner",
    "gitea_repo",
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check whether gitea state backend pilot prerequisites are satisfied."
    )
    parser.add_argument(
        "--out",
        default="benchmarks/results/gitea_state_pilot_readiness.json",
        help="Output JSON artifact path.",
    )
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Exit non-zero when readiness checks fail.",
    )
    return parser.parse_args()


def _env(name: str) -> str:
    return str(os.environ.get(name) or "").strip()


def collect_runtime_inputs() -> Dict[str, Any]:
    return {
        "state_backend_mode": _env("ORKET_STATE_BACKEND_MODE") or "local",
        "pilot_enabled": _env("ORKET_ENABLE_GITEA_STATE_PILOT").lower() in {"1", "true", "yes", "on"},
        "gitea_url": _env("ORKET_GITEA_URL"),
        "gitea_token": _env("ORKET_GITEA_TOKEN"),
        "gitea_owner": _env("ORKET_GITEA_OWNER"),
        "gitea_repo": _env("ORKET_GITEA_REPO"),
    }


def evaluate_readiness(inputs: Dict[str, Any]) -> Dict[str, Any]:
    failures: List[str] = []
    mode = str(inputs.get("state_backend_mode") or "").strip().lower()
    pilot_enabled = bool(inputs.get("pilot_enabled"))
    if mode != "gitea":
        failures.append(f"state_backend_mode must be 'gitea' (got '{mode or 'unset'}')")
    if not pilot_enabled:
        failures.append("ORKET_ENABLE_GITEA_STATE_PILOT must be enabled")

    missing = [
        key
        for key in REQUIRED_CONFIG_KEYS
        if not str(inputs.get(key) or "").strip()
    ]
    if missing:
        failures.append(f"missing required gitea config: {', '.join(missing)}")

    return {
        "ready": len(failures) == 0,
        "state_backend_mode": mode or "local",
        "pilot_enabled": pilot_enabled,
        "missing_config_keys": missing,
        "failures": failures,
    }


def main() -> int:
    args = _parse_args()
    inputs = collect_runtime_inputs()
    result = evaluate_readiness(inputs)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    if bool(args.require_ready) and not bool(result.get("ready")):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
