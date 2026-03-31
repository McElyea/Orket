from __future__ import annotations

import asyncio

import httpx

from orket.adapters.llm.local_model_provider_runtime_target import uses_runtime_managed_client


def test_uses_runtime_managed_client_accepts_default_httpx_async_client() -> None:
    """Layer: unit. Verifies default openai-compatible clients still use shared runtime targeting."""
    client = httpx.AsyncClient(base_url="http://127.0.0.1:1234/v1")
    try:
        assert uses_runtime_managed_client(provider_backend="openai_compat", client=client) is True
    finally:
        asyncio.run(client.aclose())


def test_uses_runtime_managed_client_rejects_httpx_mock_transport() -> None:
    """Layer: unit. Verifies mock openai-compatible clients do not trigger real provider warmup."""
    client = httpx.AsyncClient(
        base_url="http://127.0.0.1:1234/v1",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"ok": True})),
    )
    try:
        assert uses_runtime_managed_client(provider_backend="openai_compat", client=client) is False
    finally:
        asyncio.run(client.aclose())


def test_uses_runtime_managed_client_accepts_provider_owned_httpx_mock_transport() -> None:
    """Layer: unit. Verifies provider-owned mock clients still exercise shared runtime targeting."""
    client = httpx.AsyncClient(
        base_url="http://127.0.0.1:1234/v1",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"ok": True})),
    )
    try:
        assert (
            uses_runtime_managed_client(
                provider_backend="openai_compat",
                client=client,
                provider_managed_client_id=id(client),
            )
            is True
        )
    finally:
        asyncio.run(client.aclose())
