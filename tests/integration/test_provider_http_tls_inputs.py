"""Layer: integration. Actual verified TLS, proxy headers and captured filesystem inputs."""
import asyncio
import base64
import ssl
from pathlib import Path

import httpx
import pytest

from orket.application.services import provider_http_service as service
from orket.runtime.config.provider_runtime_target import list_provider_models
from tests.helpers.observed_http_server import observed_http_server
from tests.integration.test_provider_http_environment import _ambient_proxy, _catalog

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/provider_http"


def server_context(root=FIXTURES):
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(root / "server.pem", root / "PUBLIC-TEST-ONLY-key.pem")
    return context


@pytest.mark.parametrize("provider", ["openai_compat", "ollama"])
@pytest.mark.parametrize("mode", ["file", "directory", "file-precedence", "empty", "wrong-file", "missing-file"])
async def test_catalog_tls_uses_only_captured_trust_and_preserves_verification(tmp_path, monkeypatch, provider, mode):
    context = await asyncio.to_thread(server_context)
    ambient_log = tmp_path / "ambient-keys.log"
    _ambient_proxy(monkeypatch, "http://127.0.0.1:1")
    monkeypatch.setenv("SSL_CERT_FILE", str(FIXTURES / "ca.pem"))
    monkeypatch.setenv("SSLKEYLOGFILE", str(ambient_log))
    environments = {
        "file": {"SSL_CERT_FILE": "ca.pem"},
        "directory": {"SSL_CERT_DIR": "trust-directory"},
        "file-precedence": {"SSL_CERT_FILE": "ca.pem", "SSL_CERT_DIR": "missing-directory"},
        "empty": {}, "wrong-file": {"SSL_CERT_FILE": "unrelated-ca.pem"},
        "missing-file": {"SSL_CERT_FILE": "missing.pem"},
    }
    async with observed_http_server(_catalog(provider, "verified"), ssl_context=context) as server:
        call = list_provider_models(provider=provider, base_url=server[0], timeout_s=2,
                                    environment=environments[mode], cwd=FIXTURES)
        if mode in {"empty", "wrong-file", "missing-file"}:
            with pytest.raises(FileNotFoundError if mode == "missing-file" else httpx.ConnectError):
                await asyncio.wait_for(call, 5)
            assert server[1] == []
        else:
            assert (await asyncio.wait_for(call, 5))["models"] == ["verified"]
            assert len(server[1]) == 1
    assert not await asyncio.to_thread(ambient_log.exists)


async def test_native_setup_preserves_captured_proxy_certificate_cwd_and_keylog(tmp_path, monkeypatch):
    context = await asyncio.to_thread(server_context)
    entered, release = asyncio.Event(), asyncio.Event()
    original = service.run_owned_thread

    async def held(operation, **options):
        entered.set()
        await asyncio.wait_for(release.wait(), 5)
        return await original(operation, **options)

    monkeypatch.setattr(service, "run_owned_thread", held)
    headers = []
    async with observed_http_server(_catalog("openai_compat", "tls-proxy"), ssl_context=context,
                                    request_headers=headers) as proxy:
        proxy_url = proxy[0].replace("https://", "https://fixture-user:fixture-pass@")
        supplied = {"HTTP_PROXY": proxy_url, "SSL_CERT_FILE": "ca.pem",
                    "SSLKEYLOGFILE": str(tmp_path / "captured-keys.log")}
        monkeypatch.chdir(FIXTURES)
        operation = asyncio.create_task(list_provider_models(provider="openai_compat",
            base_url="http://unresolved-catalog.invalid/v1", timeout_s=2, api_key="public-test-api-key",
            environment=supplied))
        try:
            await asyncio.wait_for(entered.wait(), 5)
            supplied.clear()
            monkeypatch.chdir(tmp_path)
            monkeypatch.setenv("SSL_CERT_FILE", "missing.pem")
            release.set()
            result = await asyncio.wait_for(asyncio.shield(operation), 5)
            assert result["models"] == ["tls-proxy"]
            assert proxy[1] == [("GET http://unresolved-catalog.invalid/v1/models HTTP/1.1", None)]
            assert headers[0]["authorization"] == "Bearer public-test-api-key"
            assert headers[0]["proxy-authorization"] == "Basic " + base64.b64encode(
                b"fixture-user:fixture-pass").decode()
            keylog = await asyncio.to_thread((tmp_path / "captured-keys.log").read_text)
            assert "TRAFFIC_SECRET" in keylog or "CLIENT_RANDOM" in keylog
        finally:
            release.set()
            await asyncio.wait_for(asyncio.gather(operation, return_exceptions=True), 5)


async def test_catalog_redirect_does_not_forward_api_key_to_second_origin():
    second_headers = []
    async with observed_http_server(_catalog("openai_compat", "second"), request_headers=second_headers) as second:
        async def redirect(request):
            return 302, {"data": []}

        first_headers = []
        async with observed_http_server(redirect, request_headers=first_headers,
                response_headers=(("Location", second[0] + "/models"),)) as first:
            with pytest.raises(httpx.HTTPStatusError):
                await list_provider_models(provider="openai_compat", base_url=first[0], timeout_s=2,
                                           api_key="public-test-api-key", environment={})
            assert len(first[1]) == 1 and first_headers[0]["authorization"] == "Bearer public-test-api-key"
        assert not second[1] and not second_headers


async def test_concurrent_catalogs_keep_distinct_proxy_inputs():
    async with (observed_http_server(_catalog("ollama", "first")) as first,
                observed_http_server(_catalog("ollama", "second")) as second):
        results = await asyncio.wait_for(asyncio.gather(*[
            list_provider_models(provider="ollama", base_url="http://unresolved-catalog.invalid", timeout_s=2,
                                 environment={"ALL_PROXY": server[0]}) for server in (first, second)]), 5)
        assert [r["models"] for r in results] == [["first"], ["second"]]
        assert len(first[1]) == len(second[1]) == 1
