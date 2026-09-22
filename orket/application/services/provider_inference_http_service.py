"""Application HTTP ownership port bound to captured inference network inputs."""
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from orket.adapters.llm.provider_inference_client import build_provider_inference_client
from orket.application.services.provider_http_resources import ProviderHttpResources
from orket.application.services.provider_http_service import capture_provider_http_inputs


class ProviderInferenceHttpService:
    def __init__(self, *, environment: Mapping[str, str], cwd: Path):
        self._inputs = capture_provider_http_inputs(environment=environment, cwd=cwd)
        self._ollama_api_key = environment.get("OLLAMA_API_KEY")
        self._resources = ProviderHttpResources()

    def create_client(self, *, backend: str, base_url: str, timeout_s: float, connect_timeout_s: float) -> Any:
        return build_provider_inference_client(inputs=self._inputs, backend=backend, base_url=base_url,
            timeout_s=timeout_s, connect_timeout_s=connect_timeout_s, ollama_api_key=self._ollama_api_key,
            own_resource=self._resources.retain)

    async def close(self, client: Any = None) -> None:
        if client is not None:
            self._resources.retain(client)
        await self._resources.close()
