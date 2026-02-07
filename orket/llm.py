# orket/llm.py
from dataclasses import dataclass
from typing import Any, Dict, Optional, List
import subprocess
import os
from pathlib import Path
import json

from orket.logging import log_event


@dataclass
class ModelResponse:
    content: str
    raw: Dict[str, Any]


class LocalModelProvider:
    """
    Local model provider with:
      - echo mode
      - Ollama mode
      - safe environment patch for Windows
      - automatic fallback when --json is unsupported
      - unified .complete(messages) API for Agent
      - token counting when available
    """

    def __init__(self, model: str, temperature: float = 0.2, seed: Optional[int] = None):
        self.model = model
        self.temperature = temperature
        self.seed = seed

    # ----------------------------------------------------------------------
    # Agent API
    # ----------------------------------------------------------------------
    def complete(self, messages: List[Dict[str, str]]) -> ModelResponse:
        prompt = self._format_messages(messages)
        return self.invoke(prompt)

    def _format_messages(self, messages: List[Dict[str, str]]) -> str:
        model_lower = self.model.lower()
        
        # ChatML (Qwen, DeepSeek, many others)
        if any(m in model_lower for m in ["qwen", "deepseek", "yi", "internlm"]):
            return self._format_chatml(messages)
            
        # Llama-3 / 3.1
        if "llama-3" in model_lower or "llama3" in model_lower:
            return self._format_llama3(messages)
            
        # Gemma-2 / 3
        if "gemma" in model_lower:
            return self._format_gemma(messages)

        # Fallback to simple format
        parts = []
        for m in messages:
            role = m["role"].upper()
            content = m["content"]
            parts.append(f"{role}: {content}")
        return "\n\n".join(parts)

    def _format_chatml(self, messages: List[Dict[str, str]]) -> str:
        prompt = ""
        for m in messages:
            role = m["role"]
            content = m["content"]
            prompt += f"<|im_start|>{role}\n{content}<|im_end|>\n"
        prompt += "<|im_start|>assistant\n"
        return prompt

    def _format_llama3(self, messages: List[Dict[str, str]]) -> str:
        # Simplified Llama-3 header format
        prompt = "<|begin_of_text|>"
        for m in messages:
            role = m["role"]
            content = m["content"]
            prompt += f"<|start_header_id|>{role}<|end_header_id|>\n\n{content}<|eot_id|>"
        prompt += "<|start_header_id|>assistant<|end_header_id|>\n\n"
        return prompt

    def _format_gemma(self, messages: List[Dict[str, str]]) -> str:
        prompt = ""
        for m in messages:
            role = "model" if m["role"] == "assistant" else m["role"]
            content = m["content"]
            prompt += f"<start_of_turn>{role}\n{content}<end_of_turn>\n"
        prompt += "<start_of_turn>model\n"
        return prompt

    # ----------------------------------------------------------------------
    # Core invoke() with JSON fallback
    # ----------------------------------------------------------------------
    def invoke(self, prompt: str) -> ModelResponse:
        # Echo mode for debugging
        if self.model == "echo":
            return ModelResponse(
                content=f"[echo]\n{prompt}",
                raw={
                    "prompt": prompt,
                    "input_tokens": None,
                    "output_tokens": None,
                    "total_tokens": None,
                    "provider": "echo",
                    "model": self.model,
                },
            )

        # Prepare safe environment for Ollama
        safe_env = os.environ.copy()

        if not safe_env.get("USERPROFILE"):
            safe_env["USERPROFILE"] = str(Path.home())

        if not safe_env.get("HOME"):
            safe_env["HOME"] = safe_env["USERPROFILE"]

        if self.seed is not None:
            safe_env["OLLAMA_SEED"] = str(self.seed)

        # ------------------------------------------------------------------
        # Attempt JSON mode first
        # ------------------------------------------------------------------
        json_cmd = ["ollama", "run", self.model, "--json"]

        try:
            proc = subprocess.run(
                json_cmd,
                input=prompt.encode("utf-8"),
                capture_output=True,
                env=safe_env,
            )

            stderr = proc.stderr.decode("utf-8", errors="ignore")

            # Detect unsupported flag
            if "unknown flag: --json" in stderr.lower():
                raise ValueError("JSON_MODE_UNSUPPORTED")

            if proc.returncode != 0:
                raise RuntimeError(stderr)

            stdout = proc.stdout.decode("utf-8", errors="ignore")

            # Ollama streams JSON lines; take the last non-empty line as final
            lines = [l for l in stdout.splitlines() if l.strip()]
            last = lines[-1] if lines else "{}"
            data = json.loads(last)

            content = data.get("response", stdout)
            prompt_tokens = data.get("prompt_eval_count")
            completion_tokens = data.get("eval_count")
            total_tokens = None
            if isinstance(prompt_tokens, int) and isinstance(completion_tokens, int):
                total_tokens = prompt_tokens + completion_tokens

            raw = {
                "stdout": stdout,
                "ollama": data,
                "input_tokens": prompt_tokens,
                "output_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "provider": "ollama-json",
                "model": self.model,
            }

            return ModelResponse(content=content, raw=raw)

        except ValueError as e:
            # ------------------------------------------------------------------
            # JSON mode unsupported → fallback to non-JSON mode
            # ------------------------------------------------------------------
            if str(e) == "JSON_MODE_UNSUPPORTED":
                # Log fallback
                log_event(
                    "model_fallback",
                    {
                        "from_model": self.model,
                        "to_model": self.model,
                        "reason": "ollama_json_unsupported",
                    },
                    workspace=Path.cwd(),  # workspace is not known here; safe fallback
                )
                return self._invoke_no_json(prompt, safe_env)

            raise

        except FileNotFoundError:
            # Ollama not installed — fallback to echo
            return ModelResponse(
                content=f"[echo-fallback]\n{prompt}",
                raw={
                    "prompt": prompt,
                    "input_tokens": None,
                    "output_tokens": None,
                    "total_tokens": None,
                    "provider": "echo-fallback",
                    "model": self.model,
                },
            )

    # ----------------------------------------------------------------------
    # Fallback: non-JSON mode (no token counts)
    # ----------------------------------------------------------------------
    def _invoke_no_json(self, prompt: str, safe_env: Dict[str, str]) -> ModelResponse:
        cmd = ["ollama", "run", self.model]

        proc = subprocess.run(
            cmd,
            input=prompt.encode("utf-8"),
            capture_output=True,
            env=safe_env,
        )

        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.decode("utf-8", errors="ignore"))

        text = proc.stdout.decode("utf-8", errors="ignore")

        return ModelResponse(
            content=text,
            raw={
                "stdout": text,
                "input_tokens": None,
                "output_tokens": None,
                "total_tokens": None,
                "provider": "ollama",
                "model": self.model,
            },
        )
