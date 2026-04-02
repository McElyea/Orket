from __future__ import annotations

import sys
from types import SimpleNamespace
from pathlib import Path

import pytest

import orket.discovery as discovery_module
import orket.interfaces.cli as cli_module
import orket.domain.reconciler as reconciler_module


class _DummyExtensionManager:
    def list_extensions(self):
        return []


def _cli_args(**overrides) -> SimpleNamespace:
    base = {
        "command": None,
        "subcommand": None,
        "target": None,
        "seed": None,
        "ref": None,
        "epic": None,
        "card": None,
        "rock": None,
        "department": "core",
        "workspace": "workspace/default",
        "model": None,
        "build_id": None,
        "interactive_conductor": False,
        "driver_steered": False,
        "resume": None,
        "task": None,
        "board": False,
        "loop": False,
        "archive_card": [],
        "archive_build": None,
        "archive_related": [],
        "archive_reason": "manual archive",
        "replay_turn": None,
        "marshaller_request": None,
        "marshaller_proposal": [],
        "marshaller_run_id": None,
        "marshaller_allow_path": [],
        "marshaller_promote": False,
        "marshaller_actor_id": None,
        "marshaller_actor_source": "cli",
        "marshaller_branch": "main",
        "marshaller_inspect_attempt": None,
        "marshaller_list_limit": 20,
        "protocol_run_b": None,
        "protocol_events_a": None,
        "protocol_events_b": None,
        "protocol_artifacts_a": None,
        "protocol_artifacts_b": None,
        "protocol_runs_root": None,
        "protocol_campaign_run_id": [],
        "protocol_baseline_run_id": None,
        "protocol_parity_session_id": [],
        "protocol_parity_discover_limit": 200,
        "protocol_max_parity_mismatches": 0,
        "protocol_sqlite_db": None,
        "protocol_strict": False,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.mark.asyncio
async def test_cli_startup_runs_reconciliation_without_bypass(monkeypatch, capsys) -> None:
    """Layer: integration. Verifies CLI startup executes reconciliation and emits path markers."""
    startup_events = []
    reconcile_calls = []
    captures = {}

    class _FakeReconciler:
        def __init__(self, root_path=None, workspace=None):
            captures["root_path"] = root_path
            captures["workspace"] = workspace

        def reconcile_all(self):
            reconcile_calls.append("called")

    def _capture_event(event_name, payload, *args, **kwargs):
        startup_events.append((event_name, payload))

    monkeypatch.setattr(reconciler_module, "StructuralReconciler", _FakeReconciler)
    monkeypatch.setattr(discovery_module, "load_user_settings", lambda: {"setup_complete": True})
    monkeypatch.setattr(discovery_module, "log_event", _capture_event)
    monkeypatch.setattr(discovery_module, "_default_model_root", lambda: Path("/fake-root/model"))
    monkeypatch.setattr(discovery_module, "_default_workspace_root", lambda: Path("/fake-root/workspace/default"))
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
    assert captures["root_path"] == Path("/fake-root/model")
    assert captures["workspace"] == Path("/fake-root/workspace/default")
    assert ("discovery_startup_path", {"path": "reconciliation", "result": "success"}) in startup_events
    assert ("discovery_startup_path", {"path": "no_op", "reason": "setup_complete"}) in startup_events


def test_perform_first_run_onboarding_marks_first_run(monkeypatch, capsys) -> None:
    """Layer: contract. Verifies first-run onboarding status, persistence, and telemetry."""
    startup_events = []
    saved_settings = []

    def _capture_event(event_name, payload, *args, **kwargs):
        startup_events.append((event_name, payload))

    monkeypatch.setattr(discovery_module, "load_user_settings", lambda: {})
    monkeypatch.setattr(discovery_module, "save_user_settings", lambda payload: saved_settings.append(payload))
    monkeypatch.setattr(discovery_module, "log_event", _capture_event)

    result = discovery_module.perform_first_run_onboarding()
    out = capsys.readouterr().out

    assert result == "first_run_setup"
    assert saved_settings == [{"setup_complete": True, "hardware_profile": "auto-detected"}]
    assert ("discovery_startup_path", {"path": "first_run_setup", "result": "completed"}) in startup_events
    assert "python main.py --card initialize_orket" in out
    assert "python main.py --rock initialize_orket" not in out


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


def test_parse_args_hides_legacy_rock_alias_from_help(monkeypatch, capsys) -> None:
    """Layer: contract. Verifies `--rock` stays accepted as a hidden compatibility alias instead of a canonical help surface."""
    monkeypatch.setattr(sys, "argv", ["main.py", "--help"])

    with pytest.raises(SystemExit) as excinfo:
        cli_module.parse_args()

    out = capsys.readouterr().out

    assert excinfo.value.code == 0
    assert "--card" in out
    assert "--rock" not in out


@pytest.mark.asyncio
async def test_cli_startup_warns_when_reconciliation_failed(monkeypatch, capsys) -> None:
    """Layer: integration. Verifies CLI surfaces degraded startup when reconciliation fails."""
    monkeypatch.setattr(
        cli_module,
        "perform_first_run_setup",
        lambda: {"reconciliation": "failed", "onboarding": "no_op"},
    )
    monkeypatch.setattr(cli_module, "ExtensionManager", _DummyExtensionManager)
    monkeypatch.setattr(cli_module.sys, "platform", "linux")
    monkeypatch.setattr(
        cli_module,
        "parse_args",
        lambda: SimpleNamespace(command="extensions", subcommand="list"),
    )

    await cli_module.run_cli()
    captured = capsys.readouterr()

    assert "No extensions installed." in captured.out
    assert "Structural reconciliation failed; continuing in degraded mode." in captured.err


@pytest.mark.asyncio
async def test_cli_rock_runtime_preserves_flag_but_routes_directly_to_run_card(monkeypatch, capsys) -> None:
    """Layer: integration. Verifies the `--rock` CLI flag survives only as a hidden compatibility alias over the canonical card surface."""

    calls: list[tuple[str, object, object, object]] = []

    class _FakeEngine:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        async def run_card(self, card_id, build_id=None, driver_steered=False):
            calls.append(("run_card", card_id, build_id, driver_steered))
            return {"card": card_id}

        async def run_rock(self, rock_name, build_id=None, driver_steered=False):
            calls.append(("run_rock", rock_name, build_id, driver_steered))
            return {"card": rock_name}

    monkeypatch.setattr(cli_module, "perform_first_run_setup", lambda: None)
    monkeypatch.setattr(cli_module, "ExtensionManager", _DummyExtensionManager)
    monkeypatch.setattr(cli_module, "OrchestrationEngine", _FakeEngine)
    monkeypatch.setattr(cli_module, "print_orket_manifest", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli_module.sys, "platform", "linux")
    monkeypatch.setattr(
        cli_module,
        "parse_args",
        lambda: _cli_args(rock="demo-rock", build_id="build-7", driver_steered=True),
    )

    await cli_module.run_cli()
    out = capsys.readouterr().out

    assert ("run_card", "demo-rock", "build-7", True) in calls
    assert ("run_rock", "demo-rock", "build-7", True) not in calls
    assert "Running Orket Card via legacy compatibility alias --rock: demo-rock" in out
    assert "=== Card demo-rock Complete (legacy compatibility alias --rock) ===" in out
