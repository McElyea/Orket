"""Real in-memory credential fixtures and observed synchronous validation admission."""
import asyncio
import threading

import pytest

from orket.application.services.kernel_runtime_owner import KernelRuntime
from orket.kernel.v1 import nervous_system_runtime_extensions as extensions
from orket.kernel.v1.nervous_system_runtime import admit_proposal_v1


@pytest.fixture
def credential_runtime(monkeypatch):
    monkeypatch.setenv("ORKET_ENABLE_NERVOUS_SYSTEM", "true")
    monkeypatch.setenv("ORKET_ALLOW_PRE_RESOLVED_POLICY_FLAGS", "true")
    monkeypatch.setenv("ORKET_USE_TOOL_PROFILE_RESOLVER", "false")
    monkeypatch.setenv("ORKET_NERVOUS_SYSTEM_TOKEN_HMAC_KEY", "credential-fixture-before")
    owner = KernelRuntime()
    try:
        with owner.activate():
            yield owner
    finally:
        owner.close()


def admitted_request(*, session="credential-session", target="first", **flags):
    base = dict(contract_version="kernel_api/v1", session_id=session, trace_id="credential-trace")
    admitted = admit_proposal_v1({**base, "proposal": {
        "proposal_type": "action.tool_call", "payload": {"target": target, **flags}}})
    request = dict(base, proposal_digest=admitted["proposal_digest"],
        admission_decision_digest=admitted["decision_digest"], tool_name="fixture.tool",
        scope_json={"allow": ["fixture.read"]}, tool_profile_definition={"tool": "fixture.tool", "risk": "low"})
    return admitted, request


def consume_request(request, issued):
    return {**request, "token": issued["token"], "tool_profile_digest": issued["tool_profile_digest"]}


class CredentialValidationHold:
    def __init__(self, monkeypatch):
        self.entered, self.release = threading.Event(), threading.Event()
        original = extensions.get_str

        def observe(payload, key, **kwargs):
            result = original(payload, key, **kwargs)
            if key == "session_id" and not self.entered.is_set():
                self.entered.set()
                assert self.release.wait(10), "credential validation fixture was not released"
            return result

        monkeypatch.setattr(extensions, "get_str", observe)

    async def run(self, operation, mutate):
        task = asyncio.create_task(asyncio.to_thread(operation))
        try:
            assert await asyncio.wait_for(asyncio.to_thread(self.entered.wait, 10), 11)
            mutate()
        finally:
            self.release.set()
            result = await asyncio.wait_for(task, 10)
        return result
