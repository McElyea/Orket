"""Contract proof of template identity and independent preview checks; no live inference claim."""

from __future__ import annotations

import hashlib

import httpx
import pytest

from orket.adapters.llm.llama_cpp_render_verification import (
    QWEN38_TEXT_TEMPLATE_PATH,
    QWEN38_TEXT_TEMPLATE_VERSION,
    expected_text_render,
    verify_llama_cpp_render,
)
from orket.exceptions import ModelProviderError

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("fault", ["", "template", "model", "render", "token_budget"])
async def test_native_preview_identity_and_bytes(fault: str) -> None:
    messages = [{"role": "user", "content": "<tool_response>cafe\u0301\r\nunchanged </tool_response>"}]
    expected = expected_text_render(messages)

    def handle(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-key"
        if request.url.path == "/props":
            return httpx.Response(
                200,
                json={
                    "chat_template": "wrong" if fault == "template" else QWEN38_TEXT_TEMPLATE_PATH.read_text(),
                    "model_alias": "wrong" if fault == "model" else "model",
                    "build_info": "fixture",
                    "default_generation_settings": {"n_ctx": 8192},
                },
            )
        if request.url.path == "/tokenize":
            return httpx.Response(200, json={"tokens": [1] * 9000 if fault == "token_budget" else [1, 2, 3]})
        assert request.url.path == "/apply-template"
        return httpx.Response(200, json={"prompt": expected + ("wrong" if fault == "render" else "")})

    async with httpx.AsyncClient(base_url="http://localhost:8080/v1", transport=httpx.MockTransport(handle)) as client:
        call = verify_llama_cpp_render(
            client=client,
            headers={"Authorization": "Bearer test-key"},
            payload={"model": "model", "messages": messages},
            template_version=QWEN38_TEXT_TEMPLATE_VERSION,
            context_budget_tokens=8192,
        )
        if fault:
            with pytest.raises(ModelProviderError, match="E_LLAMA_CPP_"):
                await call
        else:
            evidence = await call
            assert evidence["render_verified"] is True
            assert (
                evidence["template_hash"]
                == hashlib.sha256("\n".join(line.rstrip(" \t") for line in expected.replace("\r\n", "\n").split("\n")).encode()).hexdigest()
            )


@pytest.mark.parametrize("message", [{"role": "developer", "content": "x"}, {"role": "user", "content": []}])
def test_text_template_rejects_unsupported_input(message: dict) -> None:
    with pytest.raises(ModelProviderError):
        expected_text_render([message])
