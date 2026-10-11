"""Native Ollama report transport with explicit refusal of input truncation.

The Python SDK chat API does not expose truncate/shift. This bounded non-streaming
transport uses the documented native API; streaming retains its existing SDK owner.
"""
import re

import httpx

from orket.core.contracts.model_input_budget import ModelInputBudgetError
from orket.exceptions import ModelConnectionError, ModelProviderError, ModelTimeoutError

side_effecting = True


class GovernedOllamaClient:
    def __init__(self, client: httpx.AsyncClient):
        self._http = client

    async def _json(self, method: str, path: str, **options):
        try:
            response = await self._http.request(method, path, **options)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise ModelTimeoutError("Ollama request timed out; inference was not retried") from exc
        except httpx.HTTPStatusError as exc:
            # Do not expose provider bodies or URLs, which can contain private data.
            if exc.response.status_code in {502, 503, 504}:
                raise ModelConnectionError("Ollama endpoint unavailable") from exc
            raise ModelProviderError(f"E_OLLAMA_HTTP_STATUS:{exc.response.status_code}:{path}") from exc
        except httpx.RequestError as exc:
            raise ModelConnectionError("Ollama endpoint unavailable") from exc
        payload = response.json()
        if not isinstance(payload, dict):
            raise ModelProviderError("E_OLLAMA_RESPONSE_OBJECT_REQUIRED")
        return payload

    async def chat(self, *, model, messages, options, format="", tools=None):
        version = await self._json("GET", "/api/version")
        match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:[-+].*)?", str(version.get("version", "")))
        if match is None or tuple(map(int, match.groups())) < (0, 24, 0):
            raise ModelInputBudgetError("E_OLLAMA_TRUNCATION_GUARD_UNAVAILABLE: Ollama >= 0.24.0 required")
        details = await self._json("POST", "/api/show", json={"model": model})
        info = details.get("model_info", {})
        if not isinstance(info, dict):
            raise ModelInputBudgetError("E_OLLAMA_MODEL_INFO_REQUIRED")
        limit = info.get(str(info.get("general.architecture", "")) + ".context_length")
        requested = options.get("num_ctx")
        if (not isinstance(limit, int) or isinstance(limit, bool) or not isinstance(requested, int)
                or not 0 < requested <= limit):
            raise ModelInputBudgetError(
                f"E_OLLAMA_CONTEXT_LIMIT: requested={requested}, model_limit={limit}")
        payload = dict(model=model, messages=messages, options=options, stream=False, truncate=False, shift=False)
        if format:
            payload["format"] = format
        if tools:
            payload["tools"] = tools
        return await self._json("POST", "/api/chat", json=payload)

    async def aclose(self):
        await self._http.aclose()
