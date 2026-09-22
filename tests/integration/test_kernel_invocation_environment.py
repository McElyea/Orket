"""Layer: integration. Actual nested native invocations use isolated immutable inputs."""

import asyncio

import pytest

from orket.application.services.kernel_credential_input_service import capture_credential_key
from orket.application.services.kernel_invocation_inputs import bind_kernel_environment, capture_kernel_environment
from orket.application.services.kernel_invocation_service import invoke_kernel, own_kernel_publication
from orket.kernel.v1.nervous_system_policy import capture_nervous_system_policy_inputs
from orket.kernel.v1.outbound_policy_gate import load_outbound_policy_config

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def observe():
    return (capture_credential_key(), capture_nervous_system_policy_inputs(), load_outbound_policy_config())


async def test_concurrent_nested_workers_retain_their_own_environment(monkeypatch):
    monkeypatch.setenv("ORKET_NERVOUS_SYSTEM_TOKEN_HMAC_KEY", "outside-secret")
    entered, release = asyncio.Queue(), asyncio.Event()

    async def invocation(label):
        source = {
            "ORKET_NERVOUS_SYSTEM_TOKEN_HMAC_KEY": label,
            "ORKET_ENABLE_NERVOUS_SYSTEM": "true",
            "ORKET_OUTBOUND_POLICY_PII_FIELD_PATHS": label,
        }
        snapshot = capture_kernel_environment(source)
        source["ORKET_NERVOUS_SYSTEM_TOKEN_HMAC_KEY"] = "mutated"
        assert label not in repr(snapshot)

        async def operation():
            await entered.put(label)
            await release.wait()
            return await invoke_kernel(observe)

        with bind_kernel_environment(snapshot):
            return await own_kernel_publication(operation)

    tasks = [asyncio.create_task(invocation(label)) for label in ("first-secret", "second-secret")]
    try:
        assert {await asyncio.wait_for(entered.get(), 10) for _ in tasks} == {"first-secret", "second-secret"}
        release.set()
        results = await asyncio.wait_for(asyncio.gather(*tasks), 10)
        for label, (key, policy, outbound) in zip(("first-secret", "second-secret"), results, strict=True):
            assert key == label.encode() and policy.enabled
            assert outbound["pii_field_paths"] == (label,)
        assert capture_credential_key() == b"outside-secret"
    finally:
        release.set()
        await asyncio.gather(*tasks, return_exceptions=True)


async def test_explicit_empty_snapshot_is_authoritative_and_resets_after_failure(monkeypatch):
    monkeypatch.setenv("ORKET_ENABLE_NERVOUS_SYSTEM", "true")
    snapshot = capture_kernel_environment({})
    with pytest.raises(TypeError):
        snapshot.values["ORKET_ENABLE_NERVOUS_SYSTEM"] = "true"
    with pytest.raises(RuntimeError, match="fixture-failure"), bind_kernel_environment(snapshot):
        _, policy, outbound = await invoke_kernel(observe)
        assert not policy.enabled and outbound == {}
        raise RuntimeError("fixture-failure")
    assert capture_nervous_system_policy_inputs().enabled
