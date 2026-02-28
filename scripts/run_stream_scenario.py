from __future__ import annotations

import argparse
import hashlib
import json
import os
import queue
import threading
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
        except ModuleNotFoundError as exc:  # pragma: no cover
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


def _add_violation(
    violations: list[dict[str, Any]],
    *,
    code: str,
    message: str,
    kind: str,
    data: dict[str, Any] | None = None,
) -> None:
    row: dict[str, Any] = {"code": code, "message": message, "kind": kind}
    if data:
        row["data"] = data
    violations.append(row)


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


def _receive_json_with_timeout(ws: Any, timeout_s: float) -> dict[str, Any] | None:
    out: queue.Queue = queue.Queue(maxsize=1)

    def _worker() -> None:
        try:
            event = ws.receive_json()
            out.put(("ok", event))
        except Exception as exc:  # pragma: no cover - transport exception variability
            out.put(("err", exc))

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    thread.join(timeout=max(0.0, timeout_s))
    if thread.is_alive():
        return None
    if out.empty():
        return None
    status, value = out.get()
    if status == "err":
        raise value
    return value


def run_scenario(*, scenario_path: Path, timeout_s: float = 20.0) -> dict[str, Any]:
    scenario = _parse_payload(scenario_path)
    scenario_id = str(scenario.get("scenario_id") or scenario_path.stem)
    run_id = f"run-{uuid4().hex[:12]}"
    start_wall = time.time()

    api_key = str(os.getenv("ORKET_API_KEY", "test-key")).strip() or "test-key"
    os.environ["ORKET_API_KEY"] = api_key
    os.environ["ORKET_STREAM_EVENTS_V1"] = "true"

    turn_spec = scenario.get("turn") if isinstance(scenario.get("turn"), dict) else {}
    workload_id = str(turn_spec.get("workload_id", "stream_test_v1"))
    input_config = turn_spec.get("input_config")
    if not isinstance(input_config, dict):
        input_text = turn_spec.get("input")
        input_config = {"input": input_text} if input_text is not None else {"seed": 123}
    turn_params = turn_spec.get("turn_params") if isinstance(turn_spec.get("turn_params"), dict) else {}
    cancel_at = turn_spec.get("cancel_at") if isinstance(turn_spec.get("cancel_at"), dict) else None
    finalize_explicit = bool(scenario.get("finalize_explicit", False))
    expected = scenario.get("expect") if isinstance(scenario.get("expect"), dict) else {}
    require_commit_final = bool(expected.get("require_commit_final", False))
    terminal_drain_ms = int(expected.get("terminal_drain_ms", 0) or 0)
    post_cancel_quiet_ms = int(expected.get("post_cancel_quiet_ms", 0) or 0)
    post_cancel_quiet_scope = str(expected.get("post_cancel_quiet_scope", "session")).strip().lower() or "session"
    expected_http_status = expected.get("http_status")
    error_contains = str(expected.get("error_contains", "")).strip()
    require_no_stream_events = bool(expected.get("require_no_stream_events", False))
    no_stream_window_ms = int(expected.get("no_stream_window_ms", 250) or 250)
    runtime_env = scenario.get("runtime_env") if isinstance(scenario.get("runtime_env"), dict) else {}
    for key, value in runtime_env.items():
        os.environ[str(key)] = str(value)

    app = api_module.create_api_app(project_root=Path.cwd())
    client = TestClient(app)
    checker = StreamLawChecker()
    events: list[dict[str, Any]] = []
    terminal_event: str | None = None
    commit_outcome: str | None = None
    commit_digest: str | None = None
    violations: list[dict[str, Any]] = []

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
        turn_id = ""

        if expected_http_status is not None:
            if turn_resp.status_code != int(expected_http_status):
                _add_violation(
                    violations,
                    code="E_EXPECT_HTTP_STATUS",
                    message=f"expected turn status {expected_http_status} got {turn_resp.status_code}",
                    kind="expectation",
                    data={"expected": int(expected_http_status), "got": turn_resp.status_code},
                )
        elif turn_resp.status_code != 200:
            raise RuntimeError(f"failed to begin turn: {turn_resp.status_code} {turn_resp.text}")

        if error_contains:
            if error_contains.lower() not in turn_resp.text.lower():
                _add_violation(
                    violations,
                    code="E_EXPECT_ERROR_CONTAINS",
                    message=f"expected error to contain '{error_contains}'",
                    kind="expectation",
                    data={"response": turn_resp.text},
                )

        if turn_resp.status_code == 200:
            turn_id = str(turn_resp.json()["turn_id"])
        else:
            if require_no_stream_events:
                deadline = time.time() + max(0.05, no_stream_window_ms / 1000.0)
                while True:
                    remaining = deadline - time.time()
                    if remaining <= 0:
                        break
                    quiet_event = _receive_json_with_timeout(ws, remaining)
                    if isinstance(quiet_event, dict):
                        _add_violation(
                            violations,
                            code="E_EXPECT_NO_STREAM_EVENTS",
                            message="received unexpected stream event for rejected turn",
                            kind="expectation",
                            data={"event": quiet_event, "window_ms": no_stream_window_ms},
                        )
                        break
            # Error-only scenario: no active turn loop required.
            commit_outcome = None
            commit_digest = None
            terminal_event = None

        if turn_resp.status_code == 200 and finalize_explicit:
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
        terminal_seen_at: float | None = None

        while turn_resp.status_code == 200:
            elapsed = time.time() - start_wall
            if elapsed > timeout_s:
                timeout_target = "commit_final" if require_commit_final else "terminal event"
                _add_violation(
                    violations,
                    code="E_TIMEOUT",
                    message=f"timeout waiting for {timeout_target} after {timeout_s}s",
                    kind="expectation",
                )
                break
            event = ws.receive_json()
            events.append(event)
            try:
                checker.consume(event)
            except StreamLawViolation as exc:
                _add_violation(violations, code="E_STREAM_LAW", message=str(exc), kind="law")
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
                if terminal_seen_at is None:
                    terminal_seen_at = time.time()
                if not require_commit_final:
                    if terminal_drain_ms <= 0:
                        break
                    if ((time.time() - terminal_seen_at) * 1000.0) >= terminal_drain_ms:
                        break
            if event_type == "commit_final":
                payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
                commit_outcome = str(payload.get("commit_outcome"))
                commit_digest = str(payload.get("commit_digest"))
                break

        if turn_resp.status_code == 200 and post_cancel_quiet_ms > 0:
            if not cancel_issued:
                _add_violation(
                    violations,
                    code="E_EXPECT_CANCEL_NOT_ISSUED",
                    message="post_cancel_quiet_ms set but cancel was not issued by scenario trigger",
                    kind="expectation",
                )
            else:
                deadline = time.time() + (post_cancel_quiet_ms / 1000.0)
                while True:
                    remaining = deadline - time.time()
                    if remaining <= 0:
                        break
                    quiet_event = _receive_json_with_timeout(ws, remaining)
                    if isinstance(quiet_event, dict):
                        in_scope = False
                        if post_cancel_quiet_scope == "turn":
                            in_scope = (
                                str(quiet_event.get("session_id")) == session_id
                                and str(quiet_event.get("turn_id")) == turn_id
                            )
                        else:
                            in_scope = str(quiet_event.get("session_id")) == session_id
                        if in_scope:
                            _add_violation(
                                violations,
                                code="E_EXPECT_QUIET_AFTER_CANCEL",
                                message=f"received unexpected event after cancel quiet window start: {quiet_event.get('event_type')}",
                                kind="expectation",
                                data={"event": quiet_event, "scope": post_cancel_quiet_scope},
                            )
                            break
                        # Ignore out-of-scope events and keep draining until deadline.

    expected_outcome = str(expected.get("outcome", "")).strip().lower()
    if expected_outcome and turn_resp.status_code == 200 and expected_outcome not in {"any", commit_outcome or ""}:
        _add_violation(
            violations,
            code="E_EXPECT_COMMIT_OUTCOME",
            message=f"expected commit_outcome {expected_outcome} got {commit_outcome}",
            kind="expectation",
            data={"expected": expected_outcome, "got": commit_outcome},
        )

    min_event_count = int(expected.get("min_event_count", 0) or 0)
    if min_event_count and len(events) < min_event_count:
        _add_violation(
            violations,
            code="E_EXPECT_MIN_EVENT_COUNT",
            message=f"expected at least {min_event_count} events got {len(events)}",
            kind="expectation",
            data={"expected": min_event_count, "got": len(events)},
        )

    token_delta_count = sum(1 for event in events if str(event.get("event_type")) == "token_delta")
    min_token_deltas = int(expected.get("min_token_deltas", 0) or 0)
    if min_token_deltas and token_delta_count < min_token_deltas:
        _add_violation(
            violations,
            code="E_EXPECT_MIN_TOKEN_DELTAS",
            message=f"expected at least {min_token_deltas} token_delta events got {token_delta_count}",
            kind="expectation",
            data={"expected": min_token_deltas, "got": token_delta_count},
        )

    require_dropped_seq_ranges = bool(expected.get("require_dropped_seq_ranges", False))
    has_dropped_seq_ranges = any(
        isinstance(event.get("payload"), dict) and bool(event["payload"].get("dropped_seq_ranges"))
        for event in events
    )
    if require_dropped_seq_ranges and not has_dropped_seq_ranges:
        _add_violation(
            violations,
            code="E_EXPECT_DROPPED_SEQ_RANGES",
            message="expected dropped_seq_ranges but none were observed",
            kind="expectation",
        )

    if require_commit_final and turn_resp.status_code == 200 and commit_digest is None:
        _add_violation(
            violations,
            code="E_EXPECT_COMMIT_FINAL",
            message="expected commit_final event but none was observed",
            kind="expectation",
        )

    dropped_seq_ranges_count = 0
    for event in events:
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        ranges = payload.get("dropped_seq_ranges")
        if isinstance(ranges, list):
            dropped_seq_ranges_count += len(ranges)
    min_dropped_seq_ranges_count = int(expected.get("min_dropped_seq_ranges_count", 0) or 0)
    if min_dropped_seq_ranges_count and dropped_seq_ranges_count < min_dropped_seq_ranges_count:
        _add_violation(
            violations,
            code="E_EXPECT_MIN_DROPPED_SEQ_RANGES",
            message=f"expected at least {min_dropped_seq_ranges_count} dropped seq ranges got {dropped_seq_ranges_count}",
            kind="expectation",
            data={"expected": min_dropped_seq_ranges_count, "got": dropped_seq_ranges_count},
        )

    law_checker_violations_count = sum(1 for item in violations if item.get("kind") == "law")
    law_checker_passed = law_checker_violations_count == 0

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
            "terminal_event": terminal_event,
            "commit_outcome": commit_outcome,
            "commit_digest": commit_digest,
            "event_count": len(events),
            "token_delta_count": token_delta_count,
            "has_dropped_seq_ranges": has_dropped_seq_ranges,
            "dropped_seq_ranges_count": dropped_seq_ranges_count,
            "stream_digest": _stream_digest(events),
        },
        "law_checker_passed": law_checker_passed,
        "law_checker_violations_count": law_checker_violations_count,
        "violations": violations,
        "generated_at_epoch_ms": int(time.time() * 1000),
        # Back-compat fields for existing consumers.
        "terminal_event": terminal_event,
        "commit_outcome": commit_outcome,
        "commit_digest": commit_digest,
        "event_count": len(events),
    }
    out_root = _observability_root(Path.cwd(), scenario_id, run_id)
    _write_artifacts(out_root, events=events, verdict=verdict)

    print(f"{verdict_status} scenario={scenario_id}")
    for violation in violations:
        print(f"FAIL {violation['code']} {violation['message']}")
    for event in events:
        print(_timeline_line(event))
    print(
        "SUMMARY "
        f"terminal={terminal_event or 'none'} "
        f"commit={commit_outcome or 'none'} "
        f"token_deltas={token_delta_count} "
        f"drops={dropped_seq_ranges_count} "
        f"stream_digest={verdict['observed']['stream_digest']}"
    )
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
