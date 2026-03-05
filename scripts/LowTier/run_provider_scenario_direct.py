from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from orket.streaming import CommitOrchestrator, InteractionManager, StreamBus, StreamBusConfig
from orket.streaming import StreamLawChecker, StreamLawViolation
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


def _provider_identity() -> dict[str, Any]:
    mode = str(os.getenv("ORKET_MODEL_STREAM_PROVIDER", "stub") or "stub").strip().lower()
    provider_name = str(os.getenv("ORKET_MODEL_STREAM_REAL_PROVIDER", "ollama") or "ollama").strip().lower()
    model_id = str(os.getenv("ORKET_MODEL_STREAM_REAL_MODEL_ID", "qwen2.5-coder:7b")).strip()
    if provider_name == "lmstudio":
        provider_name = "openai_compat"
    if provider_name == "ollama":
        base_url = str(os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")).strip()
    else:
        base_url = str(os.getenv("ORKET_MODEL_STREAM_OPENAI_BASE_URL", "http://127.0.0.1:1234/v1")).strip()
    if base_url and "://" not in base_url:
        base_url = f"http://{base_url}"
    streaming = False
    if provider_name == "ollama":
        streaming = True
    elif provider_name == "openai_compat":
        streaming = str(os.getenv("ORKET_MODEL_STREAM_OPENAI_USE_STREAM", "false")).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
    return {
        "provider_mode": mode,
        "provider": provider_name,
        "provider_name": provider_name,
        "base_url": base_url or None,
        "provider_base_url": base_url or None,
        "model_id": model_id or None,
        "provider_model_id": model_id or None,
        "streaming": streaming,
        "openai_compat": provider_name == "openai_compat",
    }


def _observability_root(project_root: Path, scenario_id: str, run_id: str) -> Path:
    gate_run_id = str(os.getenv("ORKET_STREAM_GATE_RUN_ID", "")).strip()
    loop_index = str(os.getenv("ORKET_STREAM_GATE_LOOP_INDEX", "")).strip()
    if gate_run_id:
        base = project_root / "workspace" / "observability" / "stream_scenarios" / scenario_id / gate_run_id
        if loop_index:
            return base / f"loop-{loop_index}" / run_id
        return base / run_id
    return project_root / "workspace" / "observability" / "stream_scenarios" / scenario_id / run_id


def _write_artifacts(root: Path, *, events: list[dict[str, Any]], verdict: dict[str, Any]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    events_path = root / "events.jsonl"
    with events_path.open("w", encoding="utf-8") as fh:
        for event in events:
            fh.write(json.dumps(event, sort_keys=True) + "\n")
    verdict_path = root / "verdict.json"
    verdict_path.write_text(json.dumps(verdict, indent=2, sort_keys=True), encoding="utf-8")


def _stream_digest(events: list[dict[str, Any]]) -> str:
    normalized: list[dict[str, Any]] = []
    for event in events:
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        normalized.append(
            {
                "schema_v": event.get("schema_v"),
                "session_id": event.get("session_id"),
                "turn_id": event.get("turn_id"),
                "seq": event.get("seq"),
                "event_type": event.get("event_type"),
                "payload": payload,
            }
        )
    encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


async def _run(scenario_path: Path, timeout_s: float) -> int:
    scenario = _parse_payload(scenario_path)
    scenario_id = str(scenario.get("scenario_id") or scenario_path.stem)
    run_id = f"run-{uuid4().hex[:12]}"
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

    events: list[dict[str, Any]] = []
    violations: list[dict[str, Any]] = []
    checker = StreamLawChecker()
    seen_counts: dict[str, int] = {}
    started = time.time()
    terminal = None
    commit_final = None
    cancel_issued = False
    commit_outcome = None

    while True:
        if (time.time() - started) > timeout_s:
            violations.append(
                {
                    "code": "E_TIMEOUT",
                    "message": f"timeout waiting for {'commit_final' if require_commit_final else 'terminal'} after {timeout_s}s",
                    "kind": "expectation",
                }
            )
            break
        try:
            event = await asyncio.wait_for(queue.get(), timeout=0.5)
        except asyncio.TimeoutError:
            continue

        row = event.model_dump(mode="json")
        required_fields = {"schema_v", "session_id", "turn_id", "seq", "event_type", "payload"}
        missing = sorted(field for field in required_fields if field not in row)
        if missing:
            violations.append(
                {
                    "code": "E_ENVELOPE_FIELDS",
                    "message": f"missing canonical envelope fields: {', '.join(missing)}",
                    "kind": "law",
                }
            )
            break

        events.append(row)
        event_type = str(row.get("event_type"))
        seen_counts[event_type] = seen_counts.get(event_type, 0) + 1
        print(
            f"seq={row.get('seq')} type={event_type} mono_ts_ms={row.get('mono_ts_ms')} "
            f"keys={sorted((row.get('payload') or {}).keys())}"
        )

        try:
            checker.consume(row)
        except StreamLawViolation as exc:
            violations.append({"code": "E_STREAM_LAW", "message": str(exc), "kind": "law"})
            break

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
            payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
            commit_outcome = str(payload.get("commit_outcome") or "") or None
            break

    token_delta_count = sum(1 for row in events if str(row.get("event_type")) == StreamEventType.TOKEN_DELTA.value)
    if min_token_deltas and token_delta_count < min_token_deltas:
        violations.append(
            {
                "code": "E_EXPECT_MIN_TOKEN_DELTAS",
                "message": f"expected at least {min_token_deltas} token_delta events got {token_delta_count}",
                "kind": "expectation",
            }
        )
    if require_commit_final and commit_final is None:
        violations.append(
            {
                "code": "E_EXPECT_COMMIT_FINAL",
                "message": "expected commit_final event but none was observed",
                "kind": "expectation",
            }
        )

    verdict_status = "PASS" if not violations else "FAIL"
    verdict = {
        "schema_v": "stream_verdict_v1",
        "scenario_id": scenario_id,
        "run_id": run_id,
        "status": verdict_status,
        "session_id": session_id,
        "turn_id": turn_id,
        "expected": expected,
        "observed": {
            "terminal_event": terminal,
            "commit_outcome": commit_outcome,
            "event_count": len(events),
            "token_delta_count": token_delta_count,
            "stream_digest": _stream_digest(events),
            **_provider_identity(),
        },
        "law_checker_passed": not any(v.get("kind") == "law" for v in violations),
        "law_checker_violations_count": sum(1 for v in violations if v.get("kind") == "law"),
        "violations": violations,
        "generated_at_epoch_ms": int(time.time() * 1000),
    }

    out_root = _observability_root(Path.cwd(), scenario_id, run_id)
    _write_artifacts(out_root, events=events, verdict=verdict)

    if verdict_status == "PASS":
        print(f"PASS scenario={scenario_id}")
        print(
            f"SUMMARY terminal={terminal or 'none'} commit={commit_outcome or 'none'} "
            f"token_deltas={token_delta_count}"
        )
        print(f"verdict={out_root / 'verdict.json'}")
        return 0

    print(f"FAIL scenario={scenario_id}")
    for violation in violations:
        print(f"FAIL {violation['code']} {violation['message']}")
    print(f"verdict={out_root / 'verdict.json'}")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run provider scenario directly against runtime (no API transport).")
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args()
    return asyncio.run(_run(Path(args.scenario), args.timeout))


if __name__ == "__main__":
    raise SystemExit(main())
