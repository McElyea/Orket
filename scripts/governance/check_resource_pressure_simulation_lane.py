from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from time import perf_counter
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.runtime.resource_pressure_simulation_lane import (
    resource_pressure_simulation_lane_snapshot,
    validate_resource_pressure_simulation_lane,
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
    parser = argparse.ArgumentParser(description="Check resource pressure simulation lane with stub provider.")
    parser.add_argument(
        "--out",
        default="",
        help="Optional output JSON path.",
    )
    return parser.parse_args(argv)


async def _run_lane(
    *,
    provider: StubModelStreamProvider,
    check_id: str,
    input_config: dict[str, Any],
    min_token_delta_count: int,
    max_elapsed_ms: int,
    seed: int,
) -> dict[str, Any]:
    request = ProviderTurnRequest(
        input_config={
            **input_config,
            "seed": seed,
            "force_cold_model_load": False,
        },
        turn_params={},
    )
    token_delta_count = 0
    error_terminal_count = 0
    stopped_terminal_count = 0
    started = perf_counter()
    async for event in provider.start_turn(request):
        if event.event_type == ProviderEventType.TOKEN_DELTA:
            token_delta_count += 1
        if event.event_type == ProviderEventType.ERROR:
            error_terminal_count += 1
            break
        if event.event_type == ProviderEventType.STOPPED:
            stopped_terminal_count += 1
            break
    elapsed_ms = int((perf_counter() - started) * 1000)
    ok = (
        error_terminal_count == 0
        and stopped_terminal_count == 1
        and token_delta_count >= min_token_delta_count
        and elapsed_ms <= max_elapsed_ms
    )
    return {
        "check": check_id,
        "ok": ok,
        "token_delta_count": token_delta_count,
        "min_token_delta_count": min_token_delta_count,
        "elapsed_ms": elapsed_ms,
        "max_elapsed_ms": max_elapsed_ms,
        "error_terminal_count": error_terminal_count,
        "stopped_terminal_count": stopped_terminal_count,
    }


async def _evaluate_resource_pressure_simulation_lane_async() -> dict[str, Any]:
    contract = resource_pressure_simulation_lane_snapshot()
    try:
        check_ids = list(validate_resource_pressure_simulation_lane(contract))
    except ValueError as exc:
        return {
            "schema_version": "1.0",
            "ok": False,
            "error": str(exc),
            "contract": contract,
        }

    check_map = {str(row["check_id"]): row for row in contract.get("checks", []) if isinstance(row, dict)}
    provider = StubModelStreamProvider()
    checks: list[dict[str, Any]] = []
    for index, check_id in enumerate(check_ids):
        row = check_map[check_id]
        checks.append(
            await _run_lane(
                provider=provider,
                check_id=check_id,
                input_config=dict(row.get("input_config") or {}),
                min_token_delta_count=int(row.get("min_token_delta_count") or 0),
                max_elapsed_ms=int(row.get("max_elapsed_ms") or 0),
                seed=index + 1,
            )
        )

    return {
        "schema_version": "1.0",
        "ok": all(bool(row.get("ok")) for row in checks),
        "check_count": len(check_ids),
        "checks": checks,
        "contract": contract,
    }


def evaluate_resource_pressure_simulation_lane() -> dict[str, Any]:
    return asyncio.run(_evaluate_resource_pressure_simulation_lane_async())


def check_resource_pressure_simulation_lane(*, out_path: Path | None = None) -> tuple[int, dict[str, Any]]:
    payload = evaluate_resource_pressure_simulation_lane()
    if out_path is not None:
        write_payload_with_diff_ledger(out_path, payload)
    return (0 if bool(payload.get("ok")) else 1), payload


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    out_path = Path(args.out).resolve() if str(args.out or "").strip() else None
    exit_code, payload = check_resource_pressure_simulation_lane(out_path=out_path)
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
