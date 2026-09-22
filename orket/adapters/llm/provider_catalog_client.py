"""Native TLS and HTTP client construction with no ambient network configuration."""
from __future__ import annotations

import ssl
import sys
from collections.abc import Callable

import certifi
import httpx

from orket.adapters.execution.owned_io import require_sync_context
from orket.core.contracts.provider_http import ProviderHttpInputs

side_effecting = True  # Loads trust material and constructs explicitly owned network resources.


def build_provider_catalog_client(*, inputs: ProviderHttpInputs, base_url: str, timeout_s: float,
                                  api_key: str | None, own_resource: Callable) -> httpx.AsyncClient:
    require_sync_context(code="E_PROVIDER_HTTP_REQUIRES_ASYNC_OWNER")
    # create_default_context consults ambient SSLKEYLOGFILE even with HTTPX
    # trust_env=False. Build the verified context directly from captured inputs.
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    # Preserve create_default_context's stronger certificate policy on Python3.13+.
    if sys.version_info >= (3, 13):
        context.verify_flags |= ssl.VERIFY_X509_STRICT | ssl.VERIFY_X509_PARTIAL_CHAIN
    context.load_verify_locations(
        cafile=str(inputs.certificate_file) if inputs.certificate_file else (
            None if inputs.certificate_directory else certifi.where()),
        capath=str(inputs.certificate_directory) if inputs.certificate_directory and not inputs.certificate_file else None,
    )
    context.set_alpn_protocols(["http/1.1"])
    if inputs.keylog_file:
        context.keylog_filename = str(inputs.keylog_file)
    mounts: dict[str, httpx.AsyncHTTPTransport | None] = {}
    for pattern, proxy_url in inputs.proxy_mounts:
        if proxy_url is None:
            mounts[pattern] = None
            continue
        try:
            url = httpx.URL(proxy_url)
            proxy = httpx.Proxy(url, ssl_context=context if url.scheme == "https" else None)
        except (ValueError, httpx.InvalidURL):
            raise ValueError("E_PROVIDER_HTTP_PROXY_INVALID") from None
        transport = httpx.AsyncHTTPTransport(verify=context, proxy=proxy, trust_env=False)
        own_resource(transport)
        mounts[pattern] = transport
    direct = httpx.AsyncHTTPTransport(verify=context, trust_env=False)
    own_resource(direct)
    client = httpx.AsyncClient(base_url=base_url, timeout=httpx.Timeout(timeout_s), transport=direct,
        headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
        mounts=mounts, trust_env=False, follow_redirects=False)
    own_resource(client)
    return client
