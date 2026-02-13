from dataclasses import dataclass
from typing import Any, Dict, Optional, List
import asyncio
import time

import ollama

from orket.exceptions import ModelTimeoutError, ModelConnectionError, ModelProviderError
from orket.logging import log_event


@dataclass
class ModelResponse:
    content: str
    raw: Dict[str, Any]


class LocalModelProvider:
    """
    Asynchronous local model provider using the `ollama` library.
    """

    def __init__(self, model: str, temperature: float = 0.2, seed: Optional[int] = None, timeout: int = 300):
        self.model = model
        self.temperature = temperature
        self.seed = seed
        self.timeout = timeout
        self.client = ollama.AsyncClient()

    async def complete(self, messages: List[Dict[str, str]]) -> ModelResponse:
        options = {"temperature": self.temperature}
        if self.seed is not None:
            options["seed"] = self.seed

        max_retries = 3
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                started_at = time.perf_counter()
                response = await asyncio.wait_for(
                    self.client.chat(model=self.model, messages=messages, options=options),
                    timeout=self.timeout,
                )

                content = response.get("message", {}).get("content", "")
                prompt_tokens = response.get("prompt_eval_count")
                completion_tokens = response.get("eval_count")
                total_tokens = None
                if isinstance(prompt_tokens, int) and isinstance(completion_tokens, int):
                    total_tokens = prompt_tokens + completion_tokens

                raw = {
                    "ollama": response,
                    "input_tokens": prompt_tokens,
                    "output_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "provider": "ollama-async",
                    "model": self.model,
                    "retries": attempt,
                    "latency_ms": int((time.perf_counter() - started_at) * 1000),
                    "response_chars": len(content),
                }
                return ModelResponse(content=content, raw=raw)

            except (asyncio.TimeoutError, ModelTimeoutError):
                if attempt == max_retries - 1:
                    raise ModelTimeoutError(f"Model {self.model} timed out after {max_retries} attempts.")
                log_event(
                    "model_timeout_retry",
                    {"model": self.model, "attempt": attempt + 1, "retry_delay_sec": retry_delay},
                )
            except (ConnectionError, ollama.ResponseError, ModelConnectionError) as e:
                if attempt == max_retries - 1:
                    raise ModelConnectionError(f"Ollama connection failed after {max_retries} attempts: {str(e)}")
                log_event(
                    "model_connection_retry",
                    {
                        "model": self.model,
                        "attempt": attempt + 1,
                        "retry_delay_sec": retry_delay,
                        "error": str(e),
                    },
                )
            except asyncio.CancelledError:
                raise
            except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
                raise ModelProviderError(f"Unexpected error invoking model {self.model}: {str(e)}")

            await asyncio.sleep(retry_delay)
            retry_delay *= 2

    async def clear_context(self):
        # Ollama chat calls are stateless unless using explicit sessions.
        pass

