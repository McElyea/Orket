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

from orket.runtime.long_session_soak_test_contract import (
    long_session_soak_test_contract_snapshot,
    validate_long_session_soak_test_contract,
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
    parser = argparse.ArgumentParser(description="Check long-session soak tests against stub provider.")
    parser.add_argument(
        "--out",
        default="",
        help="Optional output JSON path.",
    )
    parser.add_argument(
        "--turn-count",
        type=int,
        default=0,
        help="Optional override for turn count. Must be >= 100 when set.",
    )
    return parser.parse_args(argv)


async def _collect_turn_events(*, provider: StubModelStreamProvider, turn_index: int) -> list[str]:
    request = ProviderTurnRequest(
        input_config={
            "force_cold_model_load": (turn_index == 0),
            "delta_count": 2,
            "chunk_size": 1,
            "seed": turn_index + 1,
        },
        turn_params={},
    )
    observed: list[str] = []
    async for event in provider.start_turn(request):
        observed.append(str(event.event_type.value))
        if event.event_type in {ProviderEventType.STOPPED, ProviderEventType.ERROR}:
            break
    return observed


def _is_expected_turn_order(events: list[str]) -> bool:
    required_prefix = ["selected", "loading", "ready"]
    if len(events) < 5:
        return False
    if events[:3] != required_prefix:
        return False
    if events[-1] != "stopped":
        return False
    delta_events = [row for row in events[3:-1] if row == "token_delta"]
    return len(delta_events) >= 1 and all(row == "token_delta" for row in events[3:-1])


async def _evaluate_long_session_soak_tests_async(*, turn_count_override: int | None = None) -> dict[str, Any]:
    contract = long_session_soak_test_contract_snapshot()
    if turn_count_override is not None and turn_count_override > 0:
        contract["turn_count"] = int(turn_count_override)
    try:
        check_ids = list(validate_long_session_soak_test_contract(contract))
    except ValueError as exc:
        return {
            "schema_version": "1.0",
            "ok": False,
            "error": str(exc),
            "contract": contract,
        }

    turn_count = int(contract["turn_count"])
    provider = StubModelStreamProvider()
    terminal_counts = {"stopped": 0, "error": 0}
    event_sequences: list[list[str]] = []
    for turn_index in range(turn_count):
        events = await _collect_turn_events(provider=provider, turn_index=turn_index)
        event_sequences.append(events)
        terminal = events[-1] if events else ""
        if terminal in terminal_counts:
            terminal_counts[terminal] += 1

    order_violations = sum(1 for events in event_sequences if not _is_expected_turn_order(events))
    checks = [
        {
            "check": "stub_provider_no_error_events_across_soak_turns",
            "ok": terminal_counts["error"] == 0,
            "error_terminal_count": terminal_counts["error"],
        },
        {
            "check": "stub_provider_terminal_event_per_turn",
            "ok": terminal_counts["stopped"] == turn_count and terminal_counts["error"] == 0,
            "stopped_terminal_count": terminal_counts["stopped"],
            "turn_count": turn_count,
        },
        {
            "check": "stub_provider_event_order_stable_across_soak_turns",
            "ok": order_violations == 0,
            "order_violation_count": order_violations,
        },
    ]
    return {
        "schema_version": "1.0",
        "ok": all(bool(row.get("ok")) for row in checks),
        "check_count": len(check_ids),
        "turn_count": turn_count,
        "checks": checks,
        "contract": contract,
    }


def evaluate_long_session_soak_tests(*, turn_count_override: int | None = None) -> dict[str, Any]:
    return asyncio.run(_evaluate_long_session_soak_tests_async(turn_count_override=turn_count_override))


def check_long_session_soak_tests(
    *,
    out_path: Path | None = None,
    turn_count_override: int | None = None,
) -> tuple[int, dict[str, Any]]:
    payload = evaluate_long_session_soak_tests(turn_count_override=turn_count_override)
    if out_path is not None:
        write_payload_with_diff_ledger(out_path, payload)
    return (0 if bool(payload.get("ok")) else 1), payload


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    out_path = Path(args.out).resolve() if str(args.out or "").strip() else None
    turn_count_override = int(args.turn_count) if int(args.turn_count or 0) > 0 else None
    exit_code, payload = check_long_session_soak_tests(
        out_path=out_path,
        turn_count_override=turn_count_override,
    )
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
