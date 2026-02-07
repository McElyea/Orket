# orket/llm.py
from dataclasses import dataclass
from typing import Any, Dict, Optional, List
from pathlib import Path
import asyncio
import ollama

@dataclass
class ModelResponse:
    content: str
    raw: Dict[str, Any]

class LocalModelProvider:
    """
    Asynchronous Local model provider using the 'ollama' library.
    """

    def __init__(self, model: str, temperature: float = 0.2, seed: Optional[int] = None, timeout: int = 300):
        self.model = model
        self.temperature = temperature
        self.seed = seed
        self.timeout = timeout
        self.client = ollama.AsyncClient()

    async def complete(self, messages: List[Dict[str, str]]) -> ModelResponse:
        """
        The unified entry point for Agents.
        """
        options = {
            "temperature": self.temperature,
        }
        if self.seed is not None:
            options["seed"] = self.seed

        try:
            response = await asyncio.wait_for(
                self.client.chat(
                    model=self.model,
                    messages=messages,
                    options=options
                ),
                timeout=self.timeout
            )
            
            content = response.get("message", {}).get("content", "")
            
            # Extract token usage if available
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
            }

            return ModelResponse(content=content, raw=raw)

        except asyncio.TimeoutError:
            return ModelResponse(
                content=f"[Timeout]: Model {self.model} failed to respond within {self.timeout}s.",
                raw={"error": "timeout", "model": self.model}
            )
        except asyncio.CancelledError:
            # Re-raise to allow task cancellation to propagate
            raise
        except Exception as e:
            # Fallback for when Ollama is not running or other errors
            return ModelResponse(
                content=f"[Error invoking model {self.model}]: {str(e)}",
                raw={"error": str(e), "model": self.model}
            )