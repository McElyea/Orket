"""Per-turn streaming HTTP composition using the shared network and cleanup owners."""
import math
from contextlib import asynccontextmanager
from functools import partial

import httpx

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.llm.provider_catalog_client import build_provider_http_client
from orket.adapters.llm.provider_inference_client import build_provider_inference_client
from orket.application.services.process_input_service import capture_process_context
from orket.application.services.provider_http_resources import ProviderHttpResources
from orket.application.services.provider_http_service import capture_provider_http_inputs


class ModelStreamHttpService:
    def __init__(self, *, backend, base_url, timeout_s, environment=None, cwd=None):
        cwd, environment = capture_process_context(environment=environment, cwd=cwd)
        self._inputs = capture_provider_http_inputs(environment=environment, cwd=cwd)
        self._ollama_key = environment.get("OLLAMA_API_KEY")
        self._backend = backend
        self._base_url = base_url or environment.get("OLLAMA_HOST") or "http://127.0.0.1:11434"
        budget = float(timeout_s)
        if not math.isfinite(budget):
            raise ValueError("E_PROVIDER_HTTP_TIMEOUT_NOT_FINITE")
        self._timeout_s = max(1.0, budget)
        self.use_stream = str(environment.get("ORKET_MODEL_STREAM_OPENAI_USE_STREAM", "false")).strip().lower() in {
            "1", "true", "yes", "on"}

    def _construct(self, resources):
        if self._backend == "ollama":
            return build_provider_inference_client(inputs=self._inputs, backend="ollama", base_url=self._base_url,
                timeout_s=self._timeout_s, connect_timeout_s=self._timeout_s, ollama_api_key=self._ollama_key,
                own_resource=resources.retain)
        timeout = httpx.Timeout(timeout=self._timeout_s, connect=min(10.0, self._timeout_s),
                                read=min(10.0, self._timeout_s), write=min(10.0, self._timeout_s))
        return build_provider_http_client(inputs=self._inputs, factory=httpx.AsyncClient,
            options=dict(base_url=self._base_url, timeout=timeout, follow_redirects=False), own_resource=resources.retain)

    @asynccontextmanager
    async def open(self):
        resources = ProviderHttpResources()
        try:
            client = await run_owned_thread(partial(self._construct, resources), label="model-stream-http-construction")
            yield client, resources
        finally:
            # Includes partially acquired transports if construction cannot transfer.
            # This sits outside provider ERROR translation: close failure refuses completion.
            await resources.close()
