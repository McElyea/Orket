# orket/llm.py
from dataclasses import dataclass
from typing import Any, Dict, Optional, List
from pathlib import Path
import asyncio
import ollama
from orket.exceptions import ModelTimeoutError, ModelConnectionError, ModelProviderError

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
        The unified entry point for Agents with built-in retry logic.
        """
        options = {
            "temperature": self.temperature,
        }
        if self.seed is not None:
            options["seed"] = self.seed

        max_retries = 3
        retry_delay = 1  # seconds

        for attempt in range(max_retries):
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
                    "retries": attempt
                }

                return ModelResponse(content=content, raw=raw)

            except (asyncio.TimeoutError, ModelTimeoutError) as e:
                if attempt == max_retries - 1:
                    raise ModelTimeoutError(f"Model {self.model} timed out after {max_retries} attempts.")
                print(f"  [WARN] Model timeout on attempt {attempt + 1}. Retrying in {retry_delay}s...")
            except (ConnectionError, ollama.ResponseError, ModelConnectionError) as e:
                if attempt == max_retries - 1:
                    raise ModelConnectionError(f"Ollama connection failed after {max_retries} attempts: {str(e)}")
                print(f"  [WARN] Model connection error on attempt {attempt + 1}. Retrying in {retry_delay}s...")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                # Unexpected errors don't necessarily merit a retry unless specified
                raise ModelProviderError(f"Unexpected error invoking model {self.model}: {str(e)}")
            
                        await asyncio.sleep(retry_delay)
            
                        retry_delay *= 2  # Exponential backoff
            
            
            
                async def clear_context(self):
            
                    """
            
                    Clears any persistent context for this provider instance.
            
                    Ensures a 'fresh' memory for the next session.
            
                    """
            
                    # For Ollama, each chat() call is stateless by default unless a 
            
                    # persistent session ID is used. This hook allows for future cleanup
            
                    # logic or stateful provider implementations.
            
                    pass
            
            