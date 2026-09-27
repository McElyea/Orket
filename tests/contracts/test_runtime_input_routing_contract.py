"""Contract: selected runtime inputs cross driver and child-construction boundaries."""
# Layer: contract
from __future__ import annotations

from collections.abc import Iterator, Mapping
from types import SimpleNamespace

import pytest

from orket.application.services.runtime_construction_inputs import RuntimeConstructionInputs
from orket.driver import OrketDriver
from orket.runtime.execution.pipeline_wiring_service import PipelineWiringService

pytestmark = [pytest.mark.contract, pytest.mark.asyncio]


def _inputs(root, identity: str) -> RuntimeConstructionInputs:
    return RuntimeConstructionInputs(root.resolve(), {"INPUT_IDENTITY": identity}, "{}", "{}")


class _UnobservableEnvironment(Mapping[str, str]):
    def __init__(self) -> None:
        self.observations: list[str] = []

    def __iter__(self) -> Iterator[str]:
        self.observations.append("iter")
        raise AssertionError("ambiguous environment was observed")

    def __len__(self) -> int:
        self.observations.append("len")
        raise AssertionError("ambiguous environment was observed")

    def __getitem__(self, key: str) -> str:
        self.observations.append(f"getitem:{key}")
        raise AssertionError("ambiguous environment was observed")


class _PipelineProbe:
    def __init__(self, workspace, department="core", **options) -> None:
        self.workspace = workspace
        self.department = department
        self.options = options


def _parent(inputs: RuntimeConstructionInputs | None) -> _PipelineProbe:
    parent = object.__new__(_PipelineProbe)
    parent.db_path = "selected.sqlite3"
    parent.config_root = "selected-config"
    parent.decision_nodes = object()
    parent.runtime_inputs = object()
    parent.runtime_context = SimpleNamespace(construction_inputs=inputs)
    return parent


# Layer: contract
async def test_driver_refuses_explicit_inputs_plus_environment_before_observation(
    tmp_path, monkeypatch,
) -> None:
    selected = _inputs(tmp_path, "selected")
    environment = _UnobservableEnvironment()

    async def refuse_capture(cls, **_options):
        pytest.fail("ambiguous driver inputs cannot reach ambient capture")

    monkeypatch.setattr(RuntimeConstructionInputs, "capture_async", classmethod(refuse_capture))
    with pytest.raises(ValueError, match="^E_DRIVER_CONSTRUCTION_INPUTS_ENVIRONMENT_AMBIGUOUS$"):
        await OrketDriver.create(construction_inputs=selected, environment=environment)
    assert environment.observations == []


# Layer: contract
@pytest.mark.parametrize("selected_by", ["parent", "wiring"])
async def test_child_pipeline_uses_parent_then_wiring_default_without_recapture(
    tmp_path, monkeypatch, selected_by,
) -> None:
    parent_inputs = _inputs(tmp_path, "parent")
    wiring_inputs = _inputs(tmp_path, "wiring")
    parent = _parent(parent_inputs if selected_by == "parent" else None)
    service = PipelineWiringService(wiring_inputs)
    captures: list[dict] = []

    async def record_capture(cls, **options):
        captures.append(options)
        pytest.fail("child construction cannot recapture ambient inputs")

    monkeypatch.setattr(RuntimeConstructionInputs, "capture_async", classmethod(record_capture))
    construct = await service.prepare_sub_pipeline(
        parent_pipeline=parent, epic_workspace=tmp_path / "child", department="core")
    child = construct()
    expected = parent_inputs if selected_by == "parent" else wiring_inputs
    assert child.options["construction_inputs"] is expected
    assert child.options["pipeline_wiring_service"] is service
    assert captures == []


# Layer: contract
async def test_child_pipeline_refuses_missing_parent_and_wiring_inputs_without_recapture(
    tmp_path, monkeypatch,
) -> None:
    parent = _parent(None)
    captures: list[dict] = []

    async def record_capture(cls, **options):
        captures.append(options)
        pytest.fail("missing child authority cannot trigger ambient capture")

    monkeypatch.setattr(RuntimeConstructionInputs, "capture_async", classmethod(record_capture))
    with pytest.raises(RuntimeError, match="^E_CHILD_PIPELINE_CONSTRUCTION_INPUTS_REQUIRED$"):
        await PipelineWiringService().prepare_sub_pipeline(
            parent_pipeline=parent, epic_workspace=tmp_path / "child", department="core")
    assert captures == []
