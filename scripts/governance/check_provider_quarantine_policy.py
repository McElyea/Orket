from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.runtime.provider_quarantine_policy import (
    is_model_quarantined,
    is_provider_quarantined,
    parse_quarantined_provider_models,
    parse_quarantined_providers,
    resolve_provider_quarantine_policy,
)
from orket.runtime.provider_quarantine_policy_contract import (
    provider_quarantine_policy_contract_snapshot,
    validate_provider_quarantine_policy_contract,
)

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
    parser = argparse.ArgumentParser(description="Check provider quarantine policy contract and parser behavior.")
    parser.add_argument(
        "--out",
        default="",
        help="Optional output JSON path.",
    )
    return parser.parse_args(argv)


def evaluate_provider_quarantine_policy() -> dict[str, Any]:
    contract = provider_quarantine_policy_contract_snapshot()
    try:
        env_keys = list(validate_provider_quarantine_policy_contract(contract))
    except ValueError as exc:
        return {
            "schema_version": "1.0",
            "ok": False,
            "error": str(exc),
            "contract": contract,
        }

    policy = resolve_provider_quarantine_policy(
        environment={
            "ORKET_PROVIDER_QUARANTINE": "ollama, openai_compat",
            "ORKET_PROVIDER_MODEL_QUARANTINE": "ollama:llama3.2,openai_compat:gpt-4o-mini,invalid",
        }
    )

    checks = [
        {
            "check": "parse_quarantined_providers_basic",
            "ok": parse_quarantined_providers("ollama, openai_compat") == {"ollama", "openai_compat"},
        },
        {
            "check": "parse_quarantined_provider_models_ignores_invalid_tokens",
            "ok": parse_quarantined_provider_models("ollama:llama3.2,invalid") == {("ollama", "llama3.2")},
        },
        {
            "check": "resolve_provider_quarantine_policy_sorted",
            "ok": policy["providers"] == ["ollama", "openai_compat"],
        },
        {
            "check": "is_provider_quarantined_by_requested_or_canonical",
            "ok": is_provider_quarantined(
                requested_provider="ollama",
                canonical_provider="lmstudio",
                quarantined_providers={"ollama"},
            )
            and is_provider_quarantined(
                requested_provider="local",
                canonical_provider="openai_compat",
                quarantined_providers={"openai_compat"},
            ),
        },
        {
            "check": "is_model_quarantined_by_provider_model_pair",
            "ok": is_model_quarantined(
                requested_provider="ollama",
                canonical_provider="ollama",
                model_id="llama3.2",
                quarantined_provider_models={("ollama", "llama3.2")},
            ),
        },
    ]

    return {
        "schema_version": "1.0",
        "ok": all(bool(row.get("ok")) for row in checks),
        "env_key_count": len(env_keys),
        "check_count": len(checks),
        "checks": checks,
        "resolved_policy_sample": policy,
        "contract": contract,
    }


def check_provider_quarantine_policy(*, out_path: Path | None = None) -> tuple[int, dict[str, Any]]:
    payload = evaluate_provider_quarantine_policy()
    if out_path is not None:
        write_payload_with_diff_ledger(out_path, payload)
    return (0 if bool(payload.get("ok")) else 1), payload


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    out_path = Path(args.out).resolve() if str(args.out or "").strip() else None
    exit_code, payload = check_provider_quarantine_policy(out_path=out_path)
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
