"""Fault-injected daemon observations test ownership policy, not live Docker behavior."""
from __future__ import annotations

import asyncio
import json

import pytest

from orket.adapters.execution.fixture_docker import OWNER_LABEL, DockerObservationError, container_id
from orket.application.services.fixture_container_owner import FixtureContainerOwner
from orket.application.services.fixture_verification_service import (
    FixtureVerificationService,
    FixtureVerificationUncertain,
)
from orket.core.contracts.owned_command import OwnedCommandResult
from orket.schema import IssueVerification, VerificationScenario

pytestmark = pytest.mark.asyncio
IDENTITY = "a" * 64


def command(**overrides):
    fields = dict(returncode=0, stdout=b"", stderr=b"", reason="completed", cleanup_confirmed=True,
                  capture_complete=True, backend="windows_job", transport_pid=1, supervisor_pid=2,
                  command_pid=3, diagnostics=())
    return OwnedCommandResult(**{**fields, **overrides})


class DaemonObservations:
    def __init__(self, fault):
        self.fault = fault
        self.removed = []
        self.present = False

    async def create(self, **kwargs):
        self.present = True
        if self.fault in {"lost-create", "lost-create-no-discovery"}:
            raise DockerObservationError("controlled lost create acknowledgement")
        return IDENTITY

    async def inspect(self, identity):
        return {"Id": identity, "Name": "/test-owner", "Config": {"Labels": {
            OWNER_LABEL: "foreign" if self.fault == "foreign-owner" else "owner"}},
            "State": {"Running": self.fault == "still-running", "Status": "exited", "ExitCode": 0}}

    async def attach(self, identity, payload):
        if self.fault == "adapter-error":
            raise TypeError("controlled unexpected adapter failure after creation")
        return command(returncode=1 if self.fault == "exit-disagrees" else 0)

    async def discover(self, name):
        return [] if self.fault == "lost-create-no-discovery" else [IDENTITY]

    async def absent(self, identity):
        if self.fault == "daemon-unavailable":
            raise DockerObservationError("controlled unavailable daemon")
        return not self.present

    async def remove(self, identity):
        self.removed.append(identity)
        if self.fault == "remove-refused":
            raise DockerObservationError("controlled refused removal")
        self.present = False
        if self.fault == "lost-remove":
            raise DockerObservationError("controlled lost removal acknowledgement")


@pytest.mark.parametrize("fault,confirmed,removed,reason", [
    ("none", True, True, "completed"),
    ("lost-create", True, True, "launch_failed"),
    ("lost-create-no-discovery", False, False, "cleanup_unconfirmed"),
    ("foreign-owner", False, False, "cleanup_unconfirmed"),
    ("daemon-unavailable", False, False, "cleanup_unconfirmed"),
    ("remove-refused", False, True, "cleanup_unconfirmed"),
    ("lost-remove", True, True, "completed"),
    ("still-running", True, True, "observation_failed"),
    ("exit-disagrees", True, True, "observation_failed"),
    ("adapter-error", True, True, "launch_failed"),
])
# Layer: contract
async def test_daemon_observation_failures_preserve_ownership(tmp_path, fault, confirmed, removed, reason):
    owner = FixtureContainerOwner(workspace=tmp_path, environment={}, name="test-owner", owner_id="owner")
    adapter = DaemonObservations(fault)
    owner.adapter = adapter
    result = await owner.run(root=tmp_path, image="test", payload=b"{}", timeout_seconds=2)
    assert result.cleanup_confirmed is confirmed and result.reason == reason
    assert adapter.removed == ([IDENTITY] if removed else [])
    assert result.lifetime()["schema_version"] == "owned_container.v1"


@pytest.mark.parametrize("identity", [None, 123, "short-id", "-option"])
# Layer: contract
async def test_invalid_container_identity_is_an_observation_error(identity):
    with pytest.raises(DockerObservationError):
        container_id(identity)


# Layer: contract
async def test_unconfirmed_cleanup_cannot_publish_success(tmp_path, monkeypatch):
    directory = tmp_path / "verification"
    await asyncio.to_thread(directory.mkdir)
    await asyncio.to_thread((directory / "fixture.py").write_text, "def verify(data): return 1\n", encoding="utf-8")
    verification = IssueVerification(fixture_path="verification/fixture.py", scenarios=[
        VerificationScenario(id="one", description="unconfirmed", input_data={}, expected_output=1)])
    service = FixtureVerificationService(tmp_path, environment={})

    async def unconfirmed(*args, **kwargs):
        return command(cleanup_confirmed=False, reason="cleanup_unconfirmed", stdout=json.dumps({
            "ok": True, "results": [{"id": "one", "status": "pass", "actual_output": 1}]}).encode())

    monkeypatch.setattr(service.supervisor, "run", unconfirmed)
    with pytest.raises(FixtureVerificationUncertain) as observed:
        await service.verify(verification)
    assert observed.value.lifetime["cleanup_confirmed"] is False
    assert verification.scenarios[0].status == "pending" and verification.last_run is None
