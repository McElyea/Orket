from __future__ import annotations

import pytest

from orket.adapters.llm.local_model_provider import LocalModelProvider, ModelResponse


class _FakeClient:
    async def chat(self, model, messages, options):  # type: ignore[no-untyped-def]
        return {
            "message": {"content": "ok"},
            "prompt_eval_count": 12,
            "eval_count": 8,
            "prompt_eval_duration": 120_000_000,
            "eval_duration": 320_000_000,
            "total_duration": 500_000_000,
        }


@pytest.mark.asyncio
async def test_local_model_provider_emits_usage_and_timings_payload() -> None:
    provider = LocalModelProvider(model="dummy")
    provider.client = _FakeClient()

    response = await provider.complete([{"role": "user", "content": "hello"}])

    assert isinstance(response, ModelResponse)
    assert response.content == "ok"
    assert response.raw["usage"] == {
        "prompt_tokens": 12,
        "completion_tokens": 8,
        "total_tokens": 20,
    }
    assert response.raw["timings"] == {
        "prompt_ms": 120.0,
        "predicted_ms": 320.0,
        "total_ms": 500.0,
    }


def test_local_model_provider_ns_to_ms_is_type_strict() -> None:
    assert LocalModelProvider._ns_to_ms(1_000_000) == 1.0
    assert LocalModelProvider._ns_to_ms(2.5) == 2.5 / 1_000_000.0
    assert LocalModelProvider._ns_to_ms("bad") is None
