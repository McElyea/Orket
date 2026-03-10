from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.runtime.cold_start_truth_test_contract import (
    cold_start_truth_test_contract_snapshot,
    validate_cold_start_truth_test_contract,
)
from orket.streaming.model_provider import (
    ProviderEventType,
    ProviderTurnRequest,
    StubModelStreamProvider,
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
    parser = argparse.ArgumentParser(description="Check cold-start truth tests against stub provider.")
    parser.add_argument(
        "--out",
        default="",
        help="Optional output JSON path.",
    )
    return parser.parse_args(argv)


async def _collect_stub_events(*, force_cold_model_load: bool) -> list[dict[str, Any]]:
    provider = StubModelStreamProvider()
    request = ProviderTurnRequest(
        input_config={
            "force_cold_model_load": force_cold_model_load,
            "delta_count": 1,
            "chunk_size": 1,
            "seed": 1,
        },
        turn_params={},
    )
    observed: list[dict[str, Any]] = []
    async for event in provider.start_turn(request):
        observed.append(
            {
                "event_type": str(event.event_type.value),
                "payload": dict(event.payload),
            }
        )
        if event.event_type in {ProviderEventType.STOPPED, ProviderEventType.ERROR}:
            break
    return observed


def _event_index(events: list[dict[str, Any]], event_type: str) -> int:
    for idx, row in enumerate(events):
        if str(row.get("event_type") or "").strip() == event_type:
            return idx
    return -1


def _event_payload(events: list[dict[str, Any]], event_type: str) -> dict[str, Any]:
    for row in events:
        if str(row.get("event_type") or "").strip() == event_type:
            payload = row.get("payload")
            if isinstance(payload, dict):
                return dict(payload)
            return {}
    return {}


async def _evaluate_cold_start_truth_tests_async() -> dict[str, Any]:
    contract = cold_start_truth_test_contract_snapshot()
    try:
        check_ids = list(validate_cold_start_truth_test_contract(contract))
    except ValueError as exc:
        return {
            "schema_version": "1.0",
            "ok": False,
            "error": str(exc),
            "contract": contract,
        }

    cold_events = await _collect_stub_events(force_cold_model_load=True)
    warm_events = await _collect_stub_events(force_cold_model_load=False)
    cold_loading = _event_payload(cold_events, "loading")
    warm_loading = _event_payload(warm_events, "loading")

    checks: list[dict[str, Any]] = [
        {
            "check": "stub_cold_start_true_loading_payload",
            "ok": bool(cold_loading.get("cold_start")) is True and _as_float(cold_loading.get("progress")) == 0.0,
            "observed": cold_loading,
        },
        {
            "check": "stub_cold_start_false_loading_payload",
            "ok": bool(warm_loading.get("cold_start")) is False and _as_float(warm_loading.get("progress")) == 1.0,
            "observed": warm_loading,
        },
        {
            "check": "stub_loading_precedes_ready_event",
            "ok": _event_index(cold_events, "loading") > -1
            and _event_index(cold_events, "ready") > _event_index(cold_events, "loading")
            and _event_index(warm_events, "loading") > -1
            and _event_index(warm_events, "ready") > _event_index(warm_events, "loading"),
        },
    ]
    return {
        "schema_version": "1.0",
        "ok": all(bool(row.get("ok")) for row in checks),
        "check_count": len(check_ids),
        "checks": checks,
        "contract": contract,
    }


def evaluate_cold_start_truth_tests() -> dict[str, Any]:
    return asyncio.run(_evaluate_cold_start_truth_tests_async())


def _as_float(value: Any, *, default: float = -1.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def check_cold_start_truth_tests(*, out_path: Path | None = None) -> tuple[int, dict[str, Any]]:
    payload = evaluate_cold_start_truth_tests()
    if out_path is not None:
        write_payload_with_diff_ledger(out_path, payload)
    return (0 if bool(payload.get("ok")) else 1), payload


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    out_path = Path(args.out).resolve() if str(args.out or "").strip() else None
    exit_code, payload = check_cold_start_truth_tests(out_path=out_path)
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
