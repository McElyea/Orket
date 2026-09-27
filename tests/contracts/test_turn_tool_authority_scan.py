"""Contract: explicit captured bindings remain visible to the ownership scan."""
from __future__ import annotations

import pytest

from tests.application import test_control_plane_workload_authority_governance as governance

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("owner_import", [
    "from orket.application.services.turn_tool_control_plane_service import TurnToolControlPlaneService",
    "from orket.application.services.turn_tool_control_plane_service import TurnToolControlPlaneService as Service",
    "from .turn_control_plane_binding import TurnControlPlaneBinding",
    "from orket.application.workflows.turn_control_plane_binding import TurnControlPlaneBinding as Binding",
])
def test_scan_retains_calls_through_declared_owner_inputs(tmp_path, monkeypatch, owner_import):
    source = tmp_path / "unexpected_caller.py"
    source.write_text(
        owner_import + "\nasync def invoke(owner):\n"
        "    await owner.ensure_reentry_allowed()\n    await owner.begin_execution()\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(governance, "_iter_python_files", lambda: [source])
    monkeypatch.setattr(governance, "_relative_path", lambda _path: "unexpected_caller.py")

    callers = governance._turn_tool_control_plane_method_callers()

    assert callers == {
        "ensure_reentry_allowed": {"unexpected_caller.py"},
        "begin_execution": {"unexpected_caller.py"},
    }
    assert callers != governance.TURN_TOOL_RUNTIME_ENTRYPOINT_METHOD_OWNERS


@pytest.mark.parametrize("owner_import", [
    "from unrelated import TurnControlPlaneBinding",
    "from .turn_control_plane_binding import unrelated",
])
def test_scan_does_not_infer_a_binding_from_unrelated_imports(tmp_path, monkeypatch, owner_import):
    source = tmp_path / "unrelated.py"
    source.write_text(owner_import + "\nowner.begin_execution()\n", encoding="utf-8")
    monkeypatch.setattr(governance, "_iter_python_files", lambda: [source])
    monkeypatch.setattr(governance, "_relative_path", lambda _path: "unrelated.py")

    assert governance._turn_tool_control_plane_method_callers() == {}
