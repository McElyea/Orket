from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.interfaces.routers.extension_runtime import build_extension_runtime_router
from orket.runtime.degradation_first_ui_standard import (
    degradation_first_ui_standard_snapshot,
    validate_degradation_first_ui_standard,
)
from orket.runtime.runtime_truth_contracts import runtime_status_vocabulary_snapshot
from orket.runtime.state_transition_registry import state_transition_registry_snapshot
from orket.runtime.structured_warning_policy import structured_warning_policy_snapshot

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
    parser = argparse.ArgumentParser(description="Check degradation-first UI standard.")
    parser.add_argument(
        "--out",
        default="",
        help="Optional output JSON path.",
    )
    return parser.parse_args(argv)


def _runtime_status_vocabulary_includes_degraded() -> dict[str, Any]:
    snapshot = runtime_status_vocabulary_snapshot()
    terms = {str(token).strip() for token in snapshot.get("runtime_status_terms", []) if str(token).strip()}
    return {
        "check": "runtime_status_vocabulary_includes_degraded",
        "ok": "degraded" in terms,
    }


def _ui_state_registry_includes_degraded_state() -> dict[str, Any]:
    snapshot = state_transition_registry_snapshot()
    domains = list(snapshot.get("domains") or [])
    ui_domain = next(
        (
            row
            for row in domains
            if isinstance(row, dict) and str(row.get("domain") or "").strip() == "ui"
        ),
        None,
    )
    states = {str(token).strip() for token in (ui_domain or {}).get("states", []) if str(token).strip()}
    return {
        "check": "ui_state_registry_includes_degraded_state",
        "ok": "degraded" in states,
    }


def _structured_warning_policy_declares_runtime_degraded() -> dict[str, Any]:
    snapshot = structured_warning_policy_snapshot()
    warning_codes = {
        str(row.get("warning_code") or "").strip()
        for row in snapshot.get("warnings", [])
        if isinstance(row, dict)
    }
    return {
        "check": "structured_warning_policy_declares_runtime_degraded",
        "ok": "W_RUNTIME_DEGRADED" in warning_codes,
    }


def _extension_runtime_models_unavailable_returns_truthful_degraded_failure() -> dict[str, Any]:
    class _Service:
        async def list_models(self, *, extension_id: str, provider: str) -> dict[str, Any]:
            del extension_id
            raise RuntimeError(f"simulated-failure:{provider}")

    app = FastAPI()
    app.include_router(build_extension_runtime_router(service_getter=lambda: _Service()))
    with TestClient(app) as client:
        response = client.get("/extensions/orket.companion/runtime/models", params={"provider": "ollama"})
    payload = response.json().get("detail", {})
    return {
        "check": "extension_runtime_models_unavailable_returns_truthful_degraded_failure",
        "ok": (
            int(response.status_code) == 503
            and bool(payload.get("degraded")) is True
            and bool(payload.get("ok")) is False
            and str(payload.get("code") or "") == "E_EXTENSION_RUNTIME_MODEL_CATALOG_UNAVAILABLE"
        ),
        "status_code": int(response.status_code),
    }


def evaluate_degradation_first_ui_standard() -> dict[str, Any]:
    standard = degradation_first_ui_standard_snapshot()
    try:
        check_ids = list(validate_degradation_first_ui_standard(standard))
    except ValueError as exc:
        return {
            "schema_version": "1.0",
            "ok": False,
            "error": str(exc),
            "standard": standard,
        }

    check_map = {
        "runtime_status_vocabulary_includes_degraded": _runtime_status_vocabulary_includes_degraded,
        "ui_state_registry_includes_degraded_state": _ui_state_registry_includes_degraded_state,
        "structured_warning_policy_declares_runtime_degraded": _structured_warning_policy_declares_runtime_degraded,
        "extension_runtime_models_unavailable_returns_truthful_degraded_failure": _extension_runtime_models_unavailable_returns_truthful_degraded_failure,
    }
    checks = [check_map[check_id]() for check_id in check_ids]
    return {
        "schema_version": "1.0",
        "ok": all(bool(row.get("ok")) for row in checks),
        "check_count": len(check_ids),
        "checks": checks,
        "standard": standard,
    }


def check_degradation_first_ui_standard(*, out_path: Path | None = None) -> tuple[int, dict[str, Any]]:
    payload = evaluate_degradation_first_ui_standard()
    if out_path is not None:
        write_payload_with_diff_ledger(out_path, payload)
    return (0 if bool(payload.get("ok")) else 1), payload


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    out_path = Path(args.out).resolve() if str(args.out or "").strip() else None
    exit_code, payload = check_degradation_first_ui_standard(out_path=out_path)
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
