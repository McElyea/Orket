from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any

from orket.streaming import CommitOrchestrator, InteractionManager, StreamBus, StreamBusConfig
from orket.streaming.contracts import StreamEventType
from orket.workloads import run_builtin_workload


def _parse_payload(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix == ".json":
        raw = json.loads(text)
    elif suffix in {".yaml", ".yml"}:
        import yaml  # type: ignore

        raw = yaml.safe_load(text)
    else:
        raise ValueError(f"Unsupported scenario format: {suffix}")
    if not isinstance(raw, dict):
        raise ValueError("Scenario payload must be an object")
    return raw


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


async def _run(scenario_path: Path, timeout_s: float) -> int:
    scenario = _parse_payload(scenario_path)
    scenario_id = str(scenario.get("scenario_id") or scenario_path.stem)
    runtime_env = scenario.get("runtime_env") if isinstance(scenario.get("runtime_env"), dict) else {}
    for key, value in runtime_env.items():
        os.environ[str(key)] = str(value)

    turn = scenario.get("turn") if isinstance(scenario.get("turn"), dict) else {}
    input_config = turn.get("input_config") if isinstance(turn.get("input_config"), dict) else {}
    turn_params = turn.get("turn_params") if isinstance(turn.get("turn_params"), dict) else {}
    cancel_at = turn.get("cancel_at") if isinstance(turn.get("cancel_at"), dict) else None
    expected = scenario.get("expect") if isinstance(scenario.get("expect"), dict) else {}
    require_commit_final = bool(expected.get("require_commit_final", False))
    min_token_deltas = _int(expected.get("min_token_deltas"), 0)

    manager = InteractionManager(
        bus=StreamBus(
            StreamBusConfig(
                best_effort_max_events_per_turn=_int(os.getenv("ORKET_STREAM_BEST_EFFORT_MAX_EVENTS_PER_TURN"), 256),
                bounded_max_events_per_turn=_int(os.getenv("ORKET_STREAM_BOUNDED_MAX_EVENTS_PER_TURN"), 128),
                max_bytes_per_turn_queue=_int(os.getenv("ORKET_STREAM_MAX_BYTES_PER_TURN_QUEUE"), 1_000_000),
            )
        ),
        commit_orchestrator=CommitOrchestrator(project_root=Path.cwd()),
        project_root=Path.cwd(),
    )

    session_id = await manager.start({})
    queue = await manager.subscribe(session_id)
    turn_id = await manager.begin_turn(session_id, input_payload=input_config, turn_params=turn_params)
    context = await manager.create_context(session_id, turn_id)
    await queue.get()  # turn_accepted

    async def _runner() -> None:
        hints = await run_builtin_workload(
            workload_id="model_stream_v1",
            input_config=input_config,
            turn_params=turn_params,
            interaction_context=context,
        )
        if int(hints.get("request_cancel_turn", 0) or 0) > 0:
            await manager.cancel(turn_id)
        await manager.finalize(session_id, turn_id)

    asyncio.create_task(_runner())

    events = []
    seen_counts: dict[str, int] = {}
    started = time.time()
    terminal = None
    commit_final = None
    cancel_issued = False
    while True:
        if (time.time() - started) > timeout_s:
            print(f"FAIL scenario={scenario_id}")
            print(f"FAIL E_TIMEOUT timeout waiting for {'commit_final' if require_commit_final else 'terminal'} after {timeout_s}s")
            return 1
        try:
            event = await asyncio.wait_for(queue.get(), timeout=0.5)
        except asyncio.TimeoutError:
            continue
        row = event.model_dump(mode="json")
        events.append(row)
        event_type = str(row.get("event_type"))
        seen_counts[event_type] = seen_counts.get(event_type, 0) + 1
        print(
            f"seq={row.get('seq')} type={event_type} mono_ts_ms={row.get('mono_ts_ms')} "
            f"keys={sorted((row.get('payload') or {}).keys())}"
        )

        if cancel_at and not cancel_issued:
            trigger_type = str(cancel_at.get("event_type") or "")
            trigger_count = _int(cancel_at.get("after_count"), 1)
            if event_type == trigger_type and seen_counts[event_type] >= trigger_count:
                await manager.cancel(turn_id)
                cancel_issued = True

        if event_type in {StreamEventType.TURN_FINAL.value, StreamEventType.TURN_INTERRUPTED.value}:
            terminal = event_type
            if not require_commit_final:
                break
        if event_type == StreamEventType.COMMIT_FINAL.value:
            commit_final = row
            break

    token_delta_count = sum(1 for row in events if str(row.get("event_type")) == StreamEventType.TOKEN_DELTA.value)
    if min_token_deltas and token_delta_count < min_token_deltas:
        print(f"FAIL scenario={scenario_id}")
        print(
            f"FAIL E_EXPECT_MIN_TOKEN_DELTAS expected at least {min_token_deltas} token_delta events got {token_delta_count}"
        )
        return 1
    if require_commit_final and commit_final is None:
        print(f"FAIL scenario={scenario_id}")
        print("FAIL E_EXPECT_COMMIT_FINAL expected commit_final event but none was observed")
        return 1

    print(f"PASS scenario={scenario_id}")
    print(
        f"SUMMARY terminal={terminal or 'none'} commit={((commit_final or {}).get('payload') or {}).get('commit_outcome') or 'none'} "
        f"token_deltas={token_delta_count}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run provider scenario directly against runtime (no API transport).")
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args()
    return asyncio.run(_run(Path(args.scenario), args.timeout))


if __name__ == "__main__":
    raise SystemExit(main())
