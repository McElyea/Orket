"""Layer: integration. Actual handshakes preserve host and controlled 3.13-style TLS flags."""
import asyncio
import ssl
from types import SimpleNamespace

import httpx
import pytest

from orket.adapters.llm import provider_catalog_client as native
from orket.runtime.config.provider_runtime_target import list_provider_models
from tests.helpers.observed_http_server import observed_http_server
from tests.integration.test_provider_http_environment import _catalog
from tests.integration.test_provider_http_tls_inputs import FIXTURES, server_context

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def observe_contexts(monkeypatch):
    contexts = []
    original = ssl.SSLContext.load_verify_locations

    def observe(context, *args, **kwargs):
        contexts.append(context)
        return original(context, *args, **kwargs)

    monkeypatch.setattr(ssl.SSLContext, "load_verify_locations", observe)
    return contexts


async def test_catalog_preserves_host_default_certificate_flags(monkeypatch):
    monkeypatch.delenv("SSLKEYLOGFILE", raising=False)
    reference = await asyncio.to_thread(ssl.create_default_context, cafile=str(FIXTURES / "ca.pem"))
    context = await asyncio.to_thread(server_context)
    observed = observe_contexts(monkeypatch)
    async with observed_http_server(_catalog("ollama", "verified"), ssl_context=context) as server:
        result = await list_provider_models(provider="ollama", base_url=server[0], timeout_s=2,
            environment={"SSL_CERT_FILE": str(FIXTURES / "ca.pem")})
        assert result["models"] == ["verified"] and len(server[1]) == len(observed) == 1
        assert observed[0].verify_flags == reference.verify_flags
        assert observed[0].verify_mode == reference.verify_mode == ssl.CERT_REQUIRED
        assert observed[0].check_hostname == reference.check_hostname is True
        assert observed[0].minimum_version == reference.minimum_version


@pytest.mark.parametrize("legacy", [False, True], ids=["valid-chain", "legacy-rejected"])
async def test_catalog_retains_python313_strict_chain_validation(monkeypatch, legacy):
    # Select the documented host-version policy; the actual SSL handshake runs
    # on the current interpreter. This is not installed Python3.13 acceptance.
    monkeypatch.setattr(native, "sys", SimpleNamespace(version_info=(3, 13)), raising=False)
    root = FIXTURES / "legacy" if legacy else FIXTURES
    context = await asyncio.to_thread(server_context, root)
    observed = observe_contexts(monkeypatch)
    async with observed_http_server(_catalog("ollama", "verified"), ssl_context=context) as server:
        call = list_provider_models(provider="ollama", base_url=server[0], timeout_s=2,
            environment={"SSL_CERT_FILE": str(root / "ca.pem")})
        if legacy:
            with pytest.raises(httpx.ConnectError):
                await call
            assert not server[1]
        else:
            assert (await call)["models"] == ["verified"] and len(server[1]) == 1
        flags = ssl.VERIFY_X509_STRICT | ssl.VERIFY_X509_PARTIAL_CHAIN
        assert len(observed) == 1 and observed[0].verify_flags & flags == flags
