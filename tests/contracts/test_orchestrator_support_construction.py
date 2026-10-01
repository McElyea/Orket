"""Contract: real support constructors retain selected inputs and original failures."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from orket.application.services.dependency_manager import DependencyManager
from orket.application.services.deployment_planner import DeploymentPlanner
from orket.application.services.runtime_policy_inputs import ArchitecturePolicySnapshot
from orket.application.services.runtime_verifier import RuntimeVerifier
from orket.application.services.scaffolder import Scaffolder
from orket.application.workflows.orchestrator import Orchestrator
from tests.helpers.turn_artifacts import artifact_test_utc_now

pytestmark = pytest.mark.contract
CASES = [
    ("scaffolder", Scaffolder),
    ("dependency_manager", DependencyManager),
    ("deployment_planner", DeploymentPlanner),
    ("runtime_verifier", RuntimeVerifier),
]


def _support(tmp_path):
    return Orchestrator(
        tmp_path,
        None,
        None,
        None,
        tmp_path,
        str(tmp_path / "cards.db"),
        None,
        None,
        architecture_policy=ArchitecturePolicySnapshot(False),
        turn_clock=artifact_test_utc_now,
    ).support_services


def _record_constructor(monkeypatch, service_class):
    calls = []
    original = service_class.__init__

    def record(instance, *args, **kwargs):
        calls.append((args, kwargs))
        return original(instance, *args, **kwargs)

    monkeypatch.setattr(service_class, "__init__", record)
    return calls


def _arguments(tmp_path, kind, profile):
    arguments = dict(
        workspace_root=tmp_path,
        organization=SimpleNamespace(process_rules={}),
        project_surface_profile=profile,
        architecture_pattern="microservices",
    )
    if kind == "runtime_verifier":
        arguments.update(
            artifact_contract={"required_read_paths": ["input.txt"]},
            issue_params={"runtime_verifier": {"commands": []}},
        )
    return arguments


@pytest.mark.parametrize("kind,service_class", CASES, ids=[row[0] for row in CASES])
@pytest.mark.parametrize("error_type", [TypeError, ValueError])
def test_real_constructor_failure_is_not_retried_or_replaced(tmp_path, monkeypatch, kind, service_class, error_type):
    """The real constructor's selected-profile conversion fails after construction begins."""
    support = _support(tmp_path)
    calls = _record_constructor(monkeypatch, service_class)
    original_error = error_type("selected profile conversion failed")

    class InvalidProfile:
        def __str__(self):
            raise original_error

    observed = None
    try:
        getattr(support, "create_" + kind)(**_arguments(tmp_path, kind, InvalidProfile()))
    except (TypeError, ValueError) as error:
        observed = error
    assert len(calls) == 1, "the actual constructor must be invoked exactly once"
    assert observed is original_error, "retain the original constructor exception"


@pytest.mark.parametrize("kind,service_class", CASES, ids=[row[0] for row in CASES])
def test_real_constructor_retains_all_selected_inputs(tmp_path, monkeypatch, kind, service_class):
    support = _support(tmp_path)
    calls = _record_constructor(monkeypatch, service_class)
    arguments = _arguments(tmp_path, kind, "api_vue")
    service = getattr(support, "create_" + kind)(**arguments)
    assert len(calls) == 1
    assert isinstance(service, service_class)
    assert service.workspace_root == tmp_path
    assert service.organization is arguments["organization"]
    assert service.project_surface_profile == "api_vue"
    assert service.architecture_pattern == "microservices"
    if kind == "runtime_verifier":
        assert service.artifact_contract == arguments["artifact_contract"]
        assert service.issue_params == arguments["issue_params"]
    else:
        assert service.file_tools is calls[0][1]["file_tools"]
