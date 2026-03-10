from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.runtime.determinism_controls import resolve_network_mode
from orket.runtime.provider_quarantine_policy import (
    parse_quarantined_provider_models,
    resolve_provider_quarantine_policy,
)
from orket.runtime.runtime_config_ownership_map import validate_runtime_config_ownership_map

try:
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
except ModuleNotFoundError:  # pragma: no cover - script execution fallback
    import importlib.util

    helper_path = Path(__file__).resolve().parents[1] / "common" / "rerun_diff_ledger.py"
    spec = importlib.util.spec_from_file_location("rerun_diff_ledger", helper_path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive fallback
        raise RuntimeError(f"E_DIFF_LEDGER_HELPER_LOAD_FAILED:{helper_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    write_payload_with_diff_ledger = module.write_payload_with_diff_ledger


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check environment parity for critical runtime controls.")
    parser.add_argument(
        "--require-key",
        action="append",
        default=[],
        help="Require an environment key to be present (repeatable).",
    )
    parser.add_argument(
        "--out",
        default="",
        help="Optional output JSON path.",
    )
    return parser.parse_args(argv)


def _invalid_provider_model_quarantine_tokens(raw: str) -> list[str]:
    tokens = [str(token).strip() for token in str(raw or "").split(",") if str(token).strip()]
    invalid: list[str] = []
    for token in tokens:
        if ":" not in token:
            invalid.append(token)
            continue
        provider, model = token.split(":", 1)
        if not str(provider or "").strip() or not str(model or "").strip():
            invalid.append(token)
    return sorted(invalid)


def evaluate_environment_parity_checklist(
    *,
    environment: dict[str, str] | None = None,
    required_keys: list[str] | None = None,
) -> dict[str, Any]:
    env = environment if isinstance(environment, dict) else dict(os.environ)
    required = sorted({str(key).strip() for key in (required_keys or []) if str(key).strip()})
    checks: list[dict[str, Any]] = []

    try:
        config_keys = list(validate_runtime_config_ownership_map())
        checks.append(
            {
                "check": "runtime_config_ownership_map_valid",
                "ok": True,
                "count": len(config_keys),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "runtime_config_ownership_map_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    network_mode_raw = str(env.get("ORKET_PROTOCOL_NETWORK_MODE", "") or "").strip()
    try:
        resolved_network_mode = resolve_network_mode(network_mode_raw)
        checks.append(
            {
                "check": "protocol_network_mode_env_valid",
                "ok": True,
                "raw": network_mode_raw,
                "resolved": resolved_network_mode,
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "protocol_network_mode_env_valid",
                "ok": False,
                "raw": network_mode_raw,
                "error": str(exc),
            }
        )

    quarantine_raw = str(env.get("ORKET_PROVIDER_MODEL_QUARANTINE", "") or "").strip()
    invalid_quarantine_tokens = _invalid_provider_model_quarantine_tokens(quarantine_raw)
    parsed_quarantine = parse_quarantined_provider_models(quarantine_raw)
    checks.append(
        {
            "check": "provider_model_quarantine_env_tokens_valid",
            "ok": not invalid_quarantine_tokens,
            "parsed_count": len(parsed_quarantine),
            "invalid_tokens": invalid_quarantine_tokens,
        }
    )

    missing_required = [key for key in required if key not in env]
    checks.append(
        {
            "check": "required_env_keys_present",
            "ok": not missing_required,
            "required_keys": required,
            "missing_keys": missing_required,
        }
    )

    quarantine_policy = resolve_provider_quarantine_policy(environment=env)
    return {
        "schema_version": "1.0",
        "ok": all(bool(row.get("ok")) for row in checks),
        "checks": checks,
        "effective": {
            "provider_quarantine_count": len(quarantine_policy.get("providers", [])),
            "provider_model_quarantine_count": len(quarantine_policy.get("provider_models", [])),
        },
    }


def check_environment_parity_checklist(
    *,
    environment: dict[str, str] | None = None,
    required_keys: list[str] | None = None,
    out_path: Path | None = None,
) -> tuple[int, dict[str, Any]]:
    payload = evaluate_environment_parity_checklist(environment=environment, required_keys=required_keys)
    if out_path is not None:
        write_payload_with_diff_ledger(out_path, payload)
    return (0 if bool(payload.get("ok")) else 1), payload


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    out_path = Path(args.out).resolve() if str(args.out or "").strip() else None
    exit_code, payload = check_environment_parity_checklist(
        environment=None,
        required_keys=[str(key) for key in (args.require_key or [])],
        out_path=out_path,
    )
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
