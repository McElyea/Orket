"""Layer: integration. Real report observations feed immutable policy decisions."""

import asyncio
import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from orket.adapters.storage.runtime_policy_reader import read_runtime_policy_document
from orket.application.services.runtime_policy import resolve_architecture_mode, runtime_policy_options
from orket.application.services.runtime_policy_input_service import RuntimePolicyInputService
from orket.application.services.runtime_policy_inputs import ArchitecturePolicySnapshot, RuntimePolicySnapshot
from orket.application.workflows.orchestrator import Orchestrator
from tests.helpers.turn_artifacts import artifact_test_utc_now
from tests.integration.test_runtime_policy_request_inputs import _unlock_payload

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
@pytest.mark.parametrize("document,expected", [
    (None, False), ("{", False), ("[]", False), ('{"unlocked":true}', False),
    (json.dumps(_unlock_payload(False)), False), (json.dumps(_unlock_payload(True)), True),
])
async def test_reports_keep_readiness_interpretation(tmp_path, document, expected):
    report = tmp_path / "unlock.json"
    if document is not None:
        await asyncio.to_thread(report.write_text, document, encoding="utf-8")
    service = RuntimePolicyInputService(environment={"ORKET_MICROSERVICES_UNLOCK_REPORT": "unlock.json"},
                                        invocation_root=tmp_path)
    observed = await service.observe_runtime()
    assert observed.architecture.microservices_unlocked is expected
    assert observed.microservices_pilot_stable is False
    assert resolve_architecture_mode("microservices", policy=observed.architecture) == (
        "force_microservices" if expected else "force_monolith")


@pytest.mark.asyncio
@pytest.mark.parametrize("override,expected", [
    ("1", True), (" true ", True), ("yes", True), ("ON", True),
    ("0", False), (" false ", False), ("no", False), ("OFF", False),
])
async def test_override_avoids_unused_report_reads(tmp_path, override, expected):
    # A directory fails if either unused report is opened, without mocked reads.
    environment = {"ORKET_ENABLE_MICROSERVICES": override,
                   "ORKET_MICROSERVICES_UNLOCK_REPORT": str(tmp_path),
                   "ORKET_MICROSERVICES_PILOT_STABILITY_REPORT": str(tmp_path)}
    service = RuntimePolicyInputService(environment=environment, invocation_root=tmp_path)
    assert (await service.observe_architecture_async()).microservices_unlocked is expected


@pytest.mark.asyncio
async def test_observation_binds_environment_root_and_each_report_once(tmp_path, monkeypatch):
    report = tmp_path / "combined.json"
    payload = dict(_unlock_payload(True), stable=True, artifact_count=1, required_consecutive=1,
                   checks=[{"stable": True, "failures": []}])
    await asyncio.to_thread(report.write_text, json.dumps(payload), encoding="utf-8")
    environment = {"ORKET_MICROSERVICES_UNLOCK_REPORT": "combined.json",
                   "ORKET_MICROSERVICES_PILOT_STABILITY_REPORT": "combined.json"}
    service = RuntimePolicyInputService(environment=environment, invocation_root=tmp_path)
    environment["ORKET_ENABLE_MICROSERVICES"] = "false"
    elsewhere = tmp_path / "elsewhere"
    await asyncio.to_thread(elsewhere.mkdir)
    monkeypatch.chdir(elsewhere)
    original, reads = Path.read_text, []

    def observe(path, *args, **kwargs):
        reads.append(path)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", observe)
    policy = await service.observe_runtime()
    assert reads == [report]
    assert policy.architecture.microservices_unlocked and policy.microservices_pilot_stable
    before = runtime_policy_options(policy)
    await asyncio.to_thread(report.write_text, "{}", encoding="utf-8")
    monkeypatch.setenv("ORKET_ENABLE_MICROSERVICES", "false")
    assert runtime_policy_options(policy) == before and reads == [report]
    with pytest.raises(TypeError):
        policy.environment["ORKET_ENABLE_MICROSERVICES"] = "false"
    with pytest.raises(FrozenInstanceError):
        policy.architecture.microservices_unlocked = False
    assert not (await service.observe_runtime()).architecture.microservices_unlocked


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["unreadable", "unicode"])
async def test_report_read_failures_propagate(tmp_path, kind):
    report = tmp_path if kind == "unreadable" else tmp_path / "invalid-encoding.json"
    if kind == "unicode":
        await asyncio.to_thread(report.write_bytes, b"\xff")
    service = RuntimePolicyInputService(environment={"ORKET_MICROSERVICES_UNLOCK_REPORT": str(report)},
                                        invocation_root=tmp_path)
    with pytest.raises(OSError if kind == "unreadable" else UnicodeDecodeError):
        await service.observe_runtime()


@pytest.mark.asyncio
async def test_native_entry_refuses_before_read_on_running_loop(tmp_path, monkeypatch):
    service = RuntimePolicyInputService(environment={}, invocation_root=tmp_path)

    def forbidden(*_args, **_kwargs):
        pytest.fail("Native admission reached a file read on the event loop")

    monkeypatch.setattr(Path, "read_text", forbidden)
    for invoke in (service.observe_architecture, lambda: read_runtime_policy_document(tmp_path / "report")):
        with pytest.raises(RuntimeError, match="E_RUNTIME_POLICY_REQUIRES_ASYNC_OWNER"):
            invoke()


def test_required_snapshot_and_root_inputs_refuse_implicit_defaults():
    """Layer: contract. Missing and malformed inputs cannot invent policy authority."""
    with pytest.raises(TypeError):
        resolve_architecture_mode("microservices")
    with pytest.raises(TypeError):
        runtime_policy_options()
    with pytest.raises(TypeError, match="E_ARCHITECTURE_POLICY_BOOLEAN_REQUIRED"):
        ArchitecturePolicySnapshot(1)
    with pytest.raises(TypeError, match="E_ARCHITECTURE_POLICY_SNAPSHOT_REQUIRED"):
        RuntimePolicySnapshot(None, False, {})
    with pytest.raises(TypeError, match="E_PILOT_STABILITY_BOOLEAN_REQUIRED"):
        RuntimePolicySnapshot(ArchitecturePolicySnapshot(False), "false", {})
    with pytest.raises(TypeError, match="E_RUNTIME_POLICY_ENVIRONMENT_STRINGS_REQUIRED"):
        RuntimePolicySnapshot(ArchitecturePolicySnapshot(False), False, {"mutable": []})
    with pytest.raises(ValueError, match="E_RUNTIME_POLICY_ROOT_ABSOLUTE_REQUIRED"):
        RuntimePolicyInputService(environment={}, invocation_root=Path("relative"))
    # Invalid collaborators deliberately fail if construction reaches any resource.
    with pytest.raises(TypeError, match="E_ARCHITECTURE_POLICY_SNAPSHOT_REQUIRED"):
        Orchestrator(None, None, None, None, None, None, None, None, architecture_policy=None, turn_clock=artifact_test_utc_now)
    with pytest.raises(TypeError, match="architecture_policy"):
        Orchestrator(None, None, None, None, None, None, None, None, turn_clock=artifact_test_utc_now)
