"""Contract: proof-script API migration with controlled model responses, not inference."""
from types import SimpleNamespace

import pytest

from scripts.proof import run_qwen38_repair_readiness as proof

pytestmark = [pytest.mark.contract, pytest.mark.asyncio]


@pytest.mark.parametrize("reject_initial", [True, False])
async def test_repair_readiness_uses_explicit_observation_and_closes_provider(monkeypatch, reject_initial):
    calls = []
    closed = []
    envelope = '{"content":"","tool_calls":[]}'

    async def complete(messages, *, runtime_context):
        calls.append((messages, dict(runtime_context)))
        content = f"```json\n{envelope}\n```" if len(calls) == 1 and reject_initial else envelope
        return SimpleNamespace(content=content, raw={})

    async def close():
        closed.append(True)

    async def create(**options):
        assert options == {"model": proof.DEFAULT_LOCAL_MODEL, "provider": "llama_cpp", "timeout": 90}
        return SimpleNamespace(complete=complete, close=close)

    monkeypatch.setattr(proof, "create_local_model_provider_async", create)
    result = await proof.prove()

    assert closed == [True]
    assert result["passed"] is reject_initial
    if reject_initial:
        assert len(calls) == 2
        assert result["deterministic_reprompt"] is True
        assert result["failure_context_included"] is True
        assert result["repairs"] == [{"attempt": 1, "response": envelope, "violations": [], "passed": True}]
    else:
        assert len(calls) == 1
        assert result["reason"] == "negative stimulus did not produce a validator rejection"
