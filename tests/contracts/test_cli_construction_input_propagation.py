"""Contract: one post-startup input object crosses CLI construction boundaries."""
# Layer: contract
from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

import orket.interfaces.cli as cli
from orket.application.services.runtime_construction_inputs import RuntimeConstructionInputs
from orket.application.services.runtime_result_lifetime import open_async_runtime_owner
from tests.interfaces.test_cli_startup_semantics import _cli_args

pytestmark = [pytest.mark.contract, pytest.mark.asyncio]


class _EngineProbe:
    def __init__(self, workspace, _department, *, construction_inputs):
        self.workspace = workspace
        self.construction_inputs = construction_inputs
        self.closed = False

    async def close(self):
        self.closed = True


class _DriverProbe:
    def __init__(self, inputs):
        self.inputs = inputs
        self.closed = False

    async def close(self):
        self.closed = True


def _inputs(tmp_path):
    return RuntimeConstructionInputs(
        tmp_path.resolve(), {"CLI_SELECTION": "selected"}, '{"selected":true}', '{"theme":"selected"}')


def _install_common(monkeypatch, selected, observed):
    async def startup(_setup):
        return {"reconciliation": "success", "onboarding": "no_op"}, selected

    async def manager(**options):
        observed.append(("manager", options["construction_inputs"]))
        return SimpleNamespace()

    async def resolve(value=".", *, invocation_root=None):
        observed.append(("path", invocation_root))
        return invocation_root / value

    async def manifest(_emit, _department):
        return None

    async def refuse_capture(cls, **_options):
        pytest.fail("CLI cannot recapture after startup")

    monkeypatch.setattr(cli, "run_startup_checks", startup)
    monkeypatch.setattr(cli, "prepare_extension_manager", manager)
    monkeypatch.setattr(cli, "_resolve_path", resolve)
    monkeypatch.setattr(cli, "emit_runtime_manifest", manifest)
    monkeypatch.setattr(cli, "OrchestrationEngine", _EngineProbe)
    monkeypatch.setattr(RuntimeConstructionInputs, "capture_async", classmethod(refuse_capture))
    monkeypatch.setattr(cli, "sys", SimpleNamespace(platform="fixture", stdout=sys.stdout, stderr=sys.stderr))


# Layer: contract
@pytest.mark.parametrize("route", ["board", "loop", "interactive"])
async def test_cli_reuses_post_startup_inputs_for_every_runtime_constructor(
    tmp_path, monkeypatch, route,
):
    selected, observed = _inputs(tmp_path), []
    _install_common(monkeypatch, selected, observed)
    engine = []
    driver = []

    class Engine(_EngineProbe):
        def __init__(self, *args, **options):
            super().__init__(*args, **options)
            engine.append(self)

    class Loop:
        @classmethod
        async def create(cls, *, construction_inputs):
            observed.append(("loop", construction_inputs))
            return cls()

        async def run_forever(self):
            return None

    async def create_driver(cls, **options):
        observed.append(("driver", options["construction_inputs"]))
        instance = _DriverProbe(options["construction_inputs"])
        driver.append(instance)
        return instance

    async def board(_engine):
        return {"rocks": []}

    async def read_line(_prompt):
        return None

    from orket import driver as driver_module
    from orket import organization_loop as loop_module

    monkeypatch.setattr(cli, "OrchestrationEngine", Engine)
    monkeypatch.setattr(cli, "read_runtime_board", board)
    monkeypatch.setattr(cli, "read_console_line", read_line)
    monkeypatch.setattr(loop_module, "OrganizationLoop", Loop)
    monkeypatch.setattr(driver_module.OrketDriver, "create", classmethod(create_driver))
    monkeypatch.setattr(cli, "parse_args", lambda: _cli_args(
        board=route == "board", loop=route == "loop"))
    assert await cli.run_cli() == 0
    assert engine and engine[0].construction_inputs is selected and engine[0].closed
    assert engine[0].workspace == selected.invocation_root / "workspace/default"
    manager_inputs = [value for kind, value in observed if kind == "manager"]
    loop_inputs = [value for kind, value in observed if kind == "loop"]
    manager_identity = len(manager_inputs) == 1 and manager_inputs[0] is selected
    loop_identity = (len(loop_inputs) == 1 and loop_inputs[0] is selected
                     if route == "loop" else not loop_inputs)
    assert manager_identity
    assert ("path", selected.invocation_root) in observed
    assert loop_identity
    assert bool(driver) == (route == "interactive")
    assert all(item.inputs is selected and item.closed for item in driver)


# Layer: contract
@pytest.mark.parametrize("route", ["extension", "protocol"])
async def test_cli_early_routes_keep_selected_path_authority(tmp_path, monkeypatch, route):
    selected, observed = _inputs(tmp_path), []
    _install_common(monkeypatch, selected, observed)

    async def workload(_args, _manager, *, invocation_root):
        observed.append(("workload-root", invocation_root))

    async def protocol(request):
        observed.append(("protocol-root", request.invocation_root))
        observed.append(("protocol-workspace", request.workspace))
        return SimpleNamespace(payload={}, strict_failure=None)

    monkeypatch.setattr(cli, "_run_extension_workload", workload)
    monkeypatch.setattr(cli, "execute_protocol_command", protocol)
    args = (_cli_args(command="run", subcommand="sample")
            if route == "extension" else _cli_args(command="protocol", subcommand="campaign"))
    monkeypatch.setattr(cli, "parse_args", lambda: args)
    assert await cli.run_cli() == 0
    manager_inputs = [value for kind, value in observed if kind == "manager"]
    manager_identity = len(manager_inputs) == 1 and manager_inputs[0] is selected
    assert manager_identity
    if route == "extension":
        assert ("workload-root", selected.invocation_root) in observed
    else:
        assert ("protocol-root", selected.invocation_root) in observed
        assert ("protocol-workspace", selected.invocation_root / "workspace/default") in observed


# Layer: contract
async def test_async_runtime_owner_keeps_close_failure_precedence():
    body_error = ValueError("controlled runtime body failure")
    close_error = OSError("controlled runtime close failure")
    close_calls = []

    class Owner:
        async def close(self):
            close_calls.append(self)
            raise close_error

    owner = Owner()

    async def create():
        return owner

    with pytest.raises(OSError) as caught:
        async with open_async_runtime_owner(create) as admitted:
            assert admitted is owner
            raise body_error

    exact_outward_failure = caught.value is close_error
    original_body_context = caught.value.__context__ is body_error
    no_explicit_cause = caught.value.__cause__ is None
    assert exact_outward_failure
    assert original_body_context
    assert no_explicit_cause
    assert close_calls == [owner]
