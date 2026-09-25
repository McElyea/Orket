# LIFECYCLE: live
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

import orket.logging as logging_module
from orket.extensions.runtime import ExtensionEngineAdapter
from scripts.security import build_tool_gate_audit as audit_module

pytestmark = pytest.mark.integration
HOLD_SECONDS = 0.75
WAIT_SECONDS = 5


@dataclass
class _AuditSettlementProbe:
    caller_thread: int
    write_entered: threading.Event = field(default_factory=threading.Event)
    release_write: threading.Event = field(default_factory=threading.Event)
    write_finished: threading.Event = field(default_factory=threading.Event)
    owner_exit_entered: threading.Event = field(default_factory=threading.Event)
    reclamation_finished: threading.Event = field(default_factory=threading.Event)
    temp_root: Path | None = None
    failed_runtime_events: int = 0
    hold_elapsed: float = 0.0
    write_succeeded: bool = False
    settled_at_owner_exit: bool | None = None
    writer_threads: list[int] = field(default_factory=list)
    timers: list[threading.Timer] = field(default_factory=list)


class _ObservedTemporaryDirectory:
    def __init__(self, owner: Any, probe: _AuditSettlementProbe) -> None:
        self._owner = owner
        self._probe = probe

    def __enter__(self) -> str:
        path = self._owner.__enter__()
        self._probe.temp_root = Path(path)
        return path

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool | None:
        self._probe.owner_exit_entered.set()
        self._probe.settled_at_owner_exit = self._probe.write_finished.is_set()
        if self._probe.write_entered.is_set():
            assert self._probe.write_finished.wait(WAIT_SECONDS), "Held runtime-event append did not finish"
        # Test-owned reclamation follows the recorded production boundary so
        # the opening failure cannot strand the real daemon or temporary root.
        logging_module._log_write_queue.join()
        try:
            return self._owner.__exit__(exc_type, exc, traceback)
        finally:
            self._probe.reclamation_finished.set()


def _install_settlement_probe(monkeypatch, tmp_path: Path) -> _AuditSettlementProbe:
    probe = _AuditSettlementProbe(caller_thread=threading.get_ident())
    original_append = logging_module._append_line_sync
    original_tempdir = audit_module.tempfile.TemporaryDirectory

    def held_append(path: Path, line: str) -> None:
        target = None if probe.temp_root is None else (
            probe.temp_root / "workspace" / "agent_output" / "observability" / "runtime_events.jsonl"
        )
        payload = json.loads(line) if target is not None and path == target else {}
        if payload.get("event") == "turn_failed":
            probe.failed_runtime_events += 1
        if payload.get("event") == "turn_failed" and probe.failed_runtime_events == 3:
            probe.writer_threads.append(threading.get_ident())
            started = time.perf_counter()
            timer = threading.Timer(HOLD_SECONDS, probe.release_write.set)
            probe.timers.append(timer)
            timer.start()
            probe.write_entered.set()
            try:
                assert probe.release_write.wait(WAIT_SECONDS), "Runtime-event append hold was not released"
                original_append(path, line)
                probe.write_succeeded = True
            finally:
                probe.hold_elapsed = time.perf_counter() - started
                probe.write_finished.set()
            return
        original_append(path, line)

    def observed_tempdir(*args: Any, **options: Any) -> _ObservedTemporaryDirectory:
        assert "dir" not in options
        owner = original_tempdir(*args, dir=tmp_path, **options)
        return _ObservedTemporaryDirectory(owner, probe)

    monkeypatch.setattr(logging_module, "_append_line_sync", held_append)
    monkeypatch.setattr(audit_module.tempfile, "TemporaryDirectory", observed_tempdir)
    return probe


def _finish_probe(probe: _AuditSettlementProbe) -> None:
    probe.release_write.set()
    for timer in probe.timers:
        timer.cancel()
        timer.join(WAIT_SECONDS)
        assert not timer.is_alive()
    logging_module._log_write_queue.join()


def _assert_probe_reclaimed(probe: _AuditSettlementProbe) -> None:
    assert probe.write_entered.is_set() and probe.write_succeeded
    assert probe.writer_threads and probe.writer_threads == [probe.writer_threads[0]]
    assert probe.writer_threads[0] != probe.caller_thread
    assert probe.hold_elapsed >= HOLD_SECONDS
    assert probe.owner_exit_entered.is_set() and probe.reclamation_finished.is_set()
    assert probe.temp_root is not None and not probe.temp_root.exists()


def _record_probe(record_property, probe: _AuditSettlementProbe, output: Path, *, close_observed: bool) -> None:
    record_property("audit_settlement_observation", json.dumps({
        "hold_reached": probe.write_entered.is_set(),
        "hold_seconds": probe.hold_elapsed,
        "append_succeeded": probe.write_succeeded,
        "native_writer": bool(probe.writer_threads and probe.writer_threads[0] != probe.caller_thread),
        "owner_exit_entered": probe.owner_exit_entered.is_set(),
        "append_settled_at_owner_exit": probe.settled_at_owner_exit,
        "cleanup_finished": probe.reclamation_finished.is_set(),
        "temp_absent": bool(probe.temp_root is not None and not probe.temp_root.exists()),
        "output_present": output.exists(),
        "expected_close_observed": close_observed,
    }, sort_keys=True))


def _assert_append_settled_at_owner_exit(probe: _AuditSettlementProbe) -> None:
    assert probe.settled_at_owner_exit, "Temporary owner exit began before the accepted runtime-event append settled"


def test_build_tool_gate_audit_writes_diff_ledger_payload(tmp_path: Path, monkeypatch, record_property) -> None:
    """Layer: integration. Verifies the canonical tool gate audit script writes a stable diff-ledger artifact."""
    out_path = tmp_path / "tool_gate_audit.json"

    probe = _install_settlement_probe(monkeypatch, tmp_path)
    try:
        exit_code = audit_module.main(["--out", str(out_path), "--strict"])
    finally:
        _finish_probe(probe)

    _assert_probe_reclaimed(probe)
    assert exit_code == 0
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "tool_gate_audit.v1"
    assert payload["gate_surface"] == "governed_turn_tool_gate_v1"
    assert isinstance(payload.get("paths"), list)
    assert any(path["dispatch_path"] == "run_card.turn_executor.tool_dispatcher" for path in payload["paths"])
    assert any(path["dispatch_path"] == "extension_engine_action_normalized_run_card" for path in payload["paths"])
    assert any(path["dispatch_path"] == "agent_run_direct_tool_execution" for path in payload["paths"])
    by_dispatch = {row["dispatch_path"]: row for row in payload["paths"]}
    for name in ("direct_turn_executor_execute_turn", "direct_tool_dispatcher_execute_tools"):
        assert by_dispatch[name]["observed_result"] == "blocked"
        assert by_dispatch[name]["side_effect_observed"] is False
    assert isinstance(payload.get("diff_ledger"), list)
    _record_probe(record_property, probe, out_path, close_observed=False)
    _assert_append_settled_at_owner_exit(probe)


def test_tool_gate_audit_cannot_publish_after_required_engine_close_fails(
    tmp_path: Path, monkeypatch, record_property,
) -> None:
    """Layer: integration. Required cleanup failure prevents a passing audit artifact."""
    original = ExtensionEngineAdapter.close

    async def refuse(self):
        await original(self)
        raise OSError("controlled audit engine close failure")

    monkeypatch.setattr(ExtensionEngineAdapter, "close", refuse)
    probe = _install_settlement_probe(monkeypatch, tmp_path)
    output = tmp_path / "failed-audit.json"
    close_error = None
    try:
        with pytest.raises(OSError, match="controlled audit engine close failure") as captured:
            audit_module.main(["--out", str(output), "--strict"])
        close_error = captured.value
    finally:
        _finish_probe(probe)

    _assert_probe_reclaimed(probe)
    assert not output.exists()
    close_observed = isinstance(close_error, OSError) and str(close_error) == "controlled audit engine close failure"
    _record_probe(record_property, probe, output, close_observed=close_observed)
    assert close_observed
    _assert_append_settled_at_owner_exit(probe)
