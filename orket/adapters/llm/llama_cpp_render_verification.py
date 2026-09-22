"""Verify the explicit text ChatML profile against the operator's native server."""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from typing import Any

import httpx

from orket.adapters.llm.prompt_canonicalization import canonicalize_prompt_text
from orket.exceptions import ModelProviderError

QWEN38_TEXT_TEMPLATE_VERSION = "orket_qwen38_text_chatml_2026_09"
QWEN38_TEXT_TEMPLATE_PATH = Path(__file__).resolve().parents[2] / "runtime/config/qwen38_text_chatml.jinja"


side_effecting = True


def expected_text_render(messages: list[dict[str, Any]]) -> str:
    """Independent reference renderer; preserve content and roles without branching on text."""
    turns = []
    for message in messages:
        if message.get("role") not in {"system", "user", "assistant", "tool"}:
            raise ModelProviderError("E_LLAMA_CPP_TEMPLATE_ROLE: unsupported role")
        if not isinstance(message.get("content"), str):
            raise ModelProviderError("E_LLAMA_CPP_TEMPLATE_CONTENT: text content required")
        turns.append(f"<|im_start|>{message['role']}\n{message['content']}<|im_end|>\n")
    return "".join(turns) + "<|im_start|>assistant\n<think>\n\n</think>\n\n"


async def verify_llama_cpp_render(
    *,
    client: httpx.AsyncClient,
    headers: dict[str, str],
    payload: dict[str, Any],
    template_version: str,
    context_budget_tokens: int = 0,
) -> dict[str, Any]:
    if template_version != QWEN38_TEXT_TEMPLATE_VERSION:
        return {}
    expected_template = await asyncio.to_thread(QWEN38_TEXT_TEMPLATE_PATH.read_bytes)
    origin = str(client.base_url).rstrip("/").removesuffix("/v1")
    props_response = await client.get(f"{origin}/props", headers=headers)
    props_response.raise_for_status()
    props = props_response.json()
    template = str(props.get("chat_template") or "").encode("utf-8")
    if template != expected_template or props.get("model_alias") != payload.get("model"):
        raise ModelProviderError("E_LLAMA_CPP_TEMPLATE_IDENTITY: launch the model with the declared text template")
    preview_response = await client.post(f"{origin}/apply-template", headers=headers, json=payload)
    preview_response.raise_for_status()
    observed = preview_response.json().get("prompt")
    expected = expected_text_render(payload["messages"])
    if observed != expected:
        raise ModelProviderError("E_LLAMA_CPP_RENDER_MISMATCH: native preview differs from the reference render")
    token_response = await client.post(
        f"{origin}/tokenize", headers=headers, json={"content": observed, "add_special": True, "parse_special": True}
    )
    token_response.raise_for_status()
    token_count = len(token_response.json()["tokens"])
    server_budget = int(props.get("default_generation_settings", {}).get("n_ctx", 0))
    budget = min(context_budget_tokens, server_budget)
    if budget <= 0 or token_count + int(payload.get("max_tokens", 0)) > budget:
        raise ModelProviderError("E_LLAMA_CPP_CONTEXT_BUDGET: native token count exceeds input/output budget")
    # LP-02 canonicalization is distinct from byte-exact renderer comparison.
    canonical = canonicalize_prompt_text(observed).encode("utf-8")
    return {
        "template_hash": hashlib.sha256(canonical).hexdigest(),
        "template_hash_alg": "sha256",
        "rendered_prompt_byte_count": len(canonical),
        "render_observability_classification": "rendered_prompt_audited",
        "render_verification_method": "provider_native_preview_byte_exact",
        "template_source_sha256": hashlib.sha256(template).hexdigest(),
        "server_build": props.get("build_info"),
        "render_verified": True,
        "token_counter_source": "llama_cpp_native_tokenize",
        "rendered_input_tokens": token_count,
        "effective_context_budget_tokens": budget,
    }
