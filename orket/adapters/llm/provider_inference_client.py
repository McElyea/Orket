"""Native inference clients reuse explicit TLS/proxy inputs and SDK public APIs."""
from collections.abc import Callable

import httpx
import ollama

from orket.adapters.llm.provider_catalog_client import build_provider_http_client
from orket.core.contracts.provider_http import ProviderHttpInputs

side_effecting = True  # Constructs clients and verified TLS through the shared native builder.


class CapturedOllamaAuth(httpx.Auth):
    def __init__(self, api_key: str | None):
        self._api_key = api_key

    def auth_flow(self, request):
        # The SDK seeds a header from os.environ. Explicit request authentication
        # overrides that seed without private SDK access or global mutation.
        request.headers.pop("Authorization", None)
        if self._api_key:
            request.headers["Authorization"] = "Bearer " + self._api_key
        yield request


def build_provider_inference_client(*, inputs: ProviderHttpInputs, backend: str, base_url: str,
                                    timeout_s: float, connect_timeout_s: float, ollama_api_key: str | None,
                                    own_resource: Callable[[object], None]) -> httpx.AsyncClient | ollama.AsyncClient:
    options: dict[str, object]
    if backend == "openai_compat":
        http_factory = httpx.AsyncClient
        options = dict(base_url=base_url, follow_redirects=False,
            timeout=httpx.Timeout(connect=connect_timeout_s, read=max(1.0, timeout_s), write=30.0, pool=10.0))
        return build_provider_http_client(inputs=inputs, factory=http_factory, options=options, own_resource=own_resource)
    elif backend == "ollama":
        ollama_factory = ollama.AsyncClient
        # Preserve the SDK redirect policy and the provider's outer generation deadline.
        options = dict(host=base_url, follow_redirects=True, timeout=None, auth=CapturedOllamaAuth(ollama_api_key))
        return build_provider_http_client(inputs=inputs, factory=ollama_factory, options=options, own_resource=own_resource)
    else:
        raise ValueError("E_PROVIDER_HTTP_BACKEND_INVALID")
