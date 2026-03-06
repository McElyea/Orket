from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path

import pytest

import orket.discovery as discovery_module
import orket.interfaces.cli as cli_module
import orket.domain.reconciler as reconciler_module


class _DummyExtensionManager:
    def list_extensions(self):
        return []


@pytest.mark.asyncio
async def test_cli_startup_runs_reconciliation_without_bypass(monkeypatch, capsys) -> None:
    """Layer: integration. Verifies CLI startup executes reconciliation and emits path markers."""
    startup_events = []
    reconcile_calls = []

    class _FakeReconciler:
        def reconcile_all(self):
            reconcile_calls.append("called")

    def _capture_event(event_name, payload, *args, **kwargs):
        startup_events.append((event_name, payload))

    monkeypatch.setattr(reconciler_module, "StructuralReconciler", _FakeReconciler)
    monkeypatch.setattr(discovery_module, "load_user_settings", lambda: {"setup_complete": True})
    monkeypatch.setattr(discovery_module, "log_event", _capture_event)
    monkeypatch.setattr(cli_module, "ExtensionManager", _DummyExtensionManager)
    monkeypatch.setattr(cli_module.sys, "platform", "linux")
    monkeypatch.setattr(
        cli_module,
        "parse_args",
        lambda: SimpleNamespace(command="extensions", subcommand="list"),
    )

    await cli_module.run_cli()
    out = capsys.readouterr().out

    assert "No extensions installed." in out
    assert reconcile_calls == ["called"]
    assert ("discovery_startup_path", {"path": "reconciliation", "result": "success"}) in startup_events
    assert ("discovery_startup_path", {"path": "no_op", "reason": "setup_complete"}) in startup_events


def test_perform_first_run_onboarding_marks_first_run(monkeypatch) -> None:
    """Layer: contract. Verifies first-run onboarding status, persistence, and telemetry."""
    startup_events = []
    saved_settings = []

    def _capture_event(event_name, payload, *args, **kwargs):
        startup_events.append((event_name, payload))

    monkeypatch.setattr(discovery_module, "load_user_settings", lambda: {})
    monkeypatch.setattr(discovery_module, "save_user_settings", lambda payload: saved_settings.append(payload))
    monkeypatch.setattr(discovery_module, "log_event", _capture_event)

    result = discovery_module.perform_first_run_onboarding()

    assert result == "first_run_setup"
    assert saved_settings == [{"setup_complete": True, "hardware_profile": "auto-detected"}]
    assert ("discovery_startup_path", {"path": "first_run_setup", "result": "completed"}) in startup_events


def test_perform_first_run_onboarding_no_op_when_complete(monkeypatch) -> None:
    """Layer: unit. Verifies onboarding no-op branch when setup already completed."""
    startup_events = []

    def _capture_event(event_name, payload, *args, **kwargs):
        startup_events.append((event_name, payload))

    monkeypatch.setattr(discovery_module, "load_user_settings", lambda: {"setup_complete": True})
    monkeypatch.setattr(discovery_module, "log_event", _capture_event)
    monkeypatch.setattr(discovery_module, "save_user_settings", lambda _payload: (_ for _ in ()).throw(AssertionError("unexpected save")))

    result = discovery_module.perform_first_run_onboarding()

    assert result == "no_op"
    assert ("discovery_startup_path", {"path": "no_op", "reason": "setup_complete"}) in startup_events
