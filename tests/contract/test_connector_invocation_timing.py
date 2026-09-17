"""Measurement provenance and unavailable timing cannot manufacture precise zero."""
from __future__ import annotations

import copy

import pytest

from orket.adapters.tools.registry import DEFAULT_BUILTIN_CONNECTOR_REGISTRY
from orket.application.services.outward_connector_service import OutwardConnectorService
from orket.core.contracts.invocation_timing import read_invocation_timing
from orket.logging import _build_runtime_event

pytestmark = pytest.mark.contract


class ReturningExecutor:
    async def invoke(self, *_args, **_kwargs):
        return {"ok": True}


@pytest.mark.asyncio
@pytest.mark.parametrize("samples,expected,reason", [
    ([100, 350100], 0.35, None), ([100, 100], 0.0, None),
    ([100, 99], None, "invalid_monotonic_interval"),
    ([100, float("nan")], None, "invalid_monotonic_sample"),
    ([True], None, "invalid_monotonic_sample"),
])
# Layer: contract
async def test_injected_monotonic_samples_preserve_precision_and_unavailability(tmp_path, samples, expected, reason):
    service = OutwardConnectorService(connector_registry=DEFAULT_BUILTIN_CONNECTOR_REGISTRY,
        workspace_root=tmp_path, executor=ReturningExecutor(), monotonic_ns=iter(samples).__next__)
    event = await service.invoke("read_file", {"path": "fixture"})
    observation = read_invocation_timing(event)
    assert event["outcome"] == "success"
    assert observation.duration_ms == expected
    assert observation.timing.clock == "injected_monotonic_ns" and observation.timing.reason == reason
    assert observation.timing.status == ("measured" if expected is not None else "unavailable")


@pytest.mark.asyncio
@pytest.mark.parametrize("fails_on", [1, 2])
# Layer: contract
async def test_unavailable_clock_does_not_reclassify_connector_return(tmp_path, fails_on):
    samples = []

    def unavailable():
        samples.append(1)
        if len(samples) == fails_on:
            raise OSError("clock unavailable")
        return 50

    service = OutwardConnectorService(connector_registry=DEFAULT_BUILTIN_CONNECTOR_REGISTRY,
        workspace_root=tmp_path, executor=ReturningExecutor(), monotonic_ns=unavailable)
    event = await service.invoke("read_file", {"path": "fixture"})
    observation = read_invocation_timing(event)
    assert event["outcome"] == "success" and observation.duration_ms is None
    assert observation.timing.status == "unavailable" and observation.timing.reason == "clock_unavailable"


@pytest.mark.asyncio
# Layer: contract
async def test_connector_exception_keeps_original_identity_and_unresolved_timing(tmp_path, caplog):
    failure = RuntimeError("execution cannot be confirmed")

    class RaisingExecutor:
        async def invoke(self, *_args, **_kwargs):
            raise failure

    service = OutwardConnectorService(connector_registry=DEFAULT_BUILTIN_CONNECTOR_REGISTRY,
        workspace_root=tmp_path, executor=RaisingExecutor(), monotonic_ns=iter([0, 37500000]).__next__)
    with pytest.raises(RuntimeError) as observed:
        await service.invoke("read_file", {"path": "fixture"})
    assert observed.value is failure
    event, = [row.orket_record["data"] for row in caplog.records if row.message == "outward_connector_interrupted"]
    assert event["observation"] == "unresolved" and "outcome" not in event
    assert read_invocation_timing(event).duration_ms == 37.5


# Layer: contract
def test_legacy_timing_is_unavailable_without_rewriting_retained_payload():
    payload = {"duration_ms": 0, "outcome": "success"}
    before = copy.deepcopy(payload)
    observation = read_invocation_timing(payload)
    assert observation.duration_ms is None and observation.timing.reason == "legacy_unmeasured"
    assert payload == before


@pytest.mark.parametrize("value,expected", [(None, None), (0, 0.0), (0.25, 0.25),
    (-1, None), (True, None), ("12", None), (float("inf"), None), (float("nan"), None)])
# Layer: contract
def test_runtime_projection_does_not_fabricate_or_truncate_duration(value, expected):
    assert _build_runtime_event("fixture", {"duration_ms": value}, "system")["duration_ms"] == expected


# Layer: contract
def test_runtime_projection_retains_timing_provenance_and_missing_stays_null():
    assert _build_runtime_event("fixture", {}, "system")["schema_version"] == "v2"
    assert _build_runtime_event("fixture", {}, "system")["duration_ms"] is None
    provenance = {"schema_version": "invocation_timing.v1", "status": "unavailable",
        "clock": None, "scope": "awaited_connector_invocation", "reason": "legacy_unmeasured"}
    projected = _build_runtime_event("fixture", {"duration_ms": None, "timing": provenance}, "system")
    assert projected["timing"] == provenance and projected["duration_ms"] is None
