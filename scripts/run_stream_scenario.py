from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient

import orket.interfaces.api as api_module
from orket.streaming import StreamLawChecker, StreamLawViolation


def _parse_payload(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix in {".json"}:
        raw = json.loads(text)
    elif suffix in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore
        except ModuleNotFoundError as exc:  # pragma: no cover - runtime dependency variation
            raise ValueError("YAML parsing support is unavailable (missing PyYAML).") from exc
        raw = yaml.safe_load(text)
    else:
        raise ValueError(f"Unsupported scenario format: {suffix}")
    if not isinstance(raw, dict):
        raise ValueError("Scenario payload must be an object")
    return raw


def _observability_root(project_root: Path, scenario_id: str, run_id: str) -> Path:
    return project_root / "workspace" / "observability" / "stream_scenarios" / scenario_id / run_id


def _write_artifacts(root: Path, *, events: list[dict[str, Any]], verdict: dict[str, Any]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    events_path = root / "events.jsonl"
    with events_path.open("w", encoding="utf-8") as fh:
        for event in events:
            fh.write(json.dumps(event, sort_keys=True) + "\n")
    verdict_path = root / "verdict.json"
    verdict_path.write_text(json.dumps(verdict, indent=2, sort_keys=True), encoding="utf-8")


def _timeline_line(event: dict[str, Any]) -> str:
    payload = event.get("payload") if isinstance(event, dict) else {}
    payload = payload if isinstance(payload, dict) else {}
    return (
        f"seq={event.get('seq')} "
        f"type={event.get('event_type')} "
        f"mono_ts_ms={event.get('mono_ts_ms')} "
        f"keys={sorted(payload.keys())}"
    )


def run_scenario(*, scenario_path: Path, timeout_s: float = 20.0) -> dict[str, Any]:
    scenario = _parse_payload(scenario_path)
    scenario_id = str(scenario.get("scenario_id") or scenario_path.stem)
    run_id = f"run-{uuid4().hex[:12]}"
    start_wall = time.time()

    api_key = str(os.getenv("ORKET_API_KEY", "test-key")).strip() or "test-key"
    os.environ["ORKET_API_KEY"] = api_key
    os.environ["ORKET_STREAM_EVENTS_V1"] = "true"

    app = api_module.create_api_app(project_root=Path.cwd())
    client = TestClient(app)
    checker = StreamLawChecker()
    events: list[dict[str, Any]] = []
    violation: str | None = None
    terminal_event: str | None = None
    commit_outcome: str | None = None
    commit_digest: str | None = None

    turn_spec = scenario.get("turn") if isinstance(scenario.get("turn"), dict) else {}
    workload_id = str(turn_spec.get("workload_id", "mystery_v1"))
    input_config = turn_spec.get("input_config")
    if not isinstance(input_config, dict):
        input_text = turn_spec.get("input")
        input_config = {"input": input_text} if input_text is not None else {"seed": 123}
    turn_params = turn_spec.get("turn_params") if isinstance(turn_spec.get("turn_params"), dict) else {}
    cancel_at = turn_spec.get("cancel_at") if isinstance(turn_spec.get("cancel_at"), dict) else None
    finalize_explicit = bool(scenario.get("finalize_explicit", False))
    expected = scenario.get("expect") if isinstance(scenario.get("expect"), dict) else {}
    expected_outcome = str(expected.get("outcome", "")).strip() or None

    start_resp = client.post(
        "/v1/interactions/sessions",
        headers={"X-API-Key": api_key},
        json={"session_params": {"scenario_id": scenario_id}},
    )
    if start_resp.status_code != 200:
        raise RuntimeError(f"failed to start interaction session: {start_resp.status_code} {start_resp.text}")
    session_id = str(start_resp.json()["session_id"])

    with client.websocket_connect(f"/ws/interactions/{session_id}?api_key={api_key}") as ws:
        turn_resp = client.post(
            f"/v1/interactions/{session_id}/turns",
            headers={"X-API-Key": api_key},
            json={
                "workload_id": workload_id,
                "input_config": input_config,
                "turn_params": turn_params,
            },
        )
        if turn_resp.status_code != 200:
            raise RuntimeError(f"failed to begin turn: {turn_resp.status_code} {turn_resp.text}")
        turn_id = str(turn_resp.json()["turn_id"])

        if finalize_explicit:
            client.post(
                f"/v1/interactions/{session_id}/finalize",
                headers={"X-API-Key": api_key},
                json={"turn_id": turn_id},
            )

        cancel_issued = False
        cancel_event_type = str(cancel_at.get("event_type")) if cancel_at else ""
        cancel_after_ms = int(cancel_at.get("after_ms", 0)) if cancel_at else 0
        cancel_after_count = int(cancel_at.get("after_count", 1)) if cancel_at else 1
        seen_event_counts: dict[str, int] = {}

        while True:
            if (time.time() - start_wall) > timeout_s:
                violation = f"timeout waiting for commit_final after {timeout_s}s"
                break
            event = ws.receive_json()
            events.append(event)
            try:
                checker.consume(event)
            except StreamLawViolation as exc:
                violation = str(exc)
                break

            event_type = str(event.get("event_type", ""))
            seen_event_counts[event_type] = seen_event_counts.get(event_type, 0) + 1

            if cancel_at and not cancel_issued and event_type == cancel_event_type:
                if seen_event_counts[event_type] >= cancel_after_count:
                    if cancel_after_ms > 0:
                        time.sleep(cancel_after_ms / 1000.0)
                    client.post(
                        f"/v1/interactions/{session_id}/cancel",
                        headers={"X-API-Key": api_key},
                        json={"turn_id": turn_id},
                    )
                    cancel_issued = True

            if event_type in {"turn_interrupted", "turn_final"}:
                terminal_event = event_type
            if event_type == "commit_final":
                payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
                commit_outcome = str(payload.get("commit_outcome"))
                commit_digest = str(payload.get("commit_digest"))
                break

    if expected_outcome and commit_outcome != expected_outcome:
        violation = violation or f"expected outcome '{expected_outcome}' got '{commit_outcome}'"

    verdict_status = "PASS" if violation is None else "FAIL"
    verdict = {
        "scenario_id": scenario_id,
        "run_id": run_id,
        "status": verdict_status,
        "session_id": session_id,
        "turn_id": turn_id,
        "terminal_event": terminal_event,
        "commit_outcome": commit_outcome,
        "commit_digest": commit_digest,
        "violations": [] if violation is None else [violation],
        "event_count": len(events),
        "generated_at_epoch_ms": int(time.time() * 1000),
    }
    out_root = _observability_root(Path.cwd(), scenario_id, run_id)
    _write_artifacts(out_root, events=events, verdict=verdict)

    print(f"{verdict_status} scenario={scenario_id}")
    if violation:
        print(f"FAIL reason={violation}")
    for event in events:
        print(_timeline_line(event))
    print(f"verdict={out_root / 'verdict.json'}")
    return verdict


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a live stream scenario with law assertions.")
    parser.add_argument("--scenario", required=True, help="Path to scenario YAML/JSON.")
    parser.add_argument("--timeout", type=float, default=20.0, help="Timeout in seconds.")
    args = parser.parse_args()
    verdict = run_scenario(scenario_path=Path(args.scenario), timeout_s=args.timeout)
    return 0 if verdict["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
