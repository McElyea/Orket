from __future__ import annotations

from types import SimpleNamespace

from orket.adapters.llm.provider_extractors import OllamaExtractor, OpenAIExtractor, extractor_for_provider


def test_provider_extractor_registry_routes_lmstudio_to_openai_shape() -> None:
    """Layer: unit. Verifies OpenAI-compatible providers use the OpenAI extractor."""
    assert isinstance(extractor_for_provider("lmstudio"), OpenAIExtractor)
    assert isinstance(extractor_for_provider("openai_compat"), OpenAIExtractor)


def test_ollama_extractor_normalizes_object_tool_calls() -> None:
    """Layer: unit. Verifies Ollama object-style tool calls normalize to OpenAI-compatible shape."""
    extractor = OllamaExtractor()
    tool_call = SimpleNamespace(
        function=SimpleNamespace(
            name="read_file",
            arguments={"path": "agent_output/a.txt"},
        )
    )

    payload = {
        "message": {"content": "ok", "tool_calls": [tool_call]},
        "prompt_eval_count": 2,
        "eval_count": 3,
        "total_duration": 10_000_000,
    }

    assert extractor.extract_content(payload) == "ok"
    assert extractor.extract_tool_calls(payload) == [
        {"type": "function", "function": {"name": "read_file", "arguments": {"path": "agent_output/a.txt"}}}
    ]
    assert extractor.extract_usage(payload) == (2, 3, 5)
    assert extractor.extract_timings(payload, latency_ms=25) == (0.0, 10.0, 10.0)


def test_ollama_extractor_accepts_chat_response_objects() -> None:
    """Layer: unit. Verifies Ollama SDK ChatResponse-style objects are normalized."""
    extractor = OllamaExtractor()
    payload = SimpleNamespace(
        message=SimpleNamespace(content='{"tool":"write_file","args":{"path":"out.txt","content":"ok"}}'),
        prompt_eval_count=5,
        eval_count=7,
        prompt_eval_duration=3_000_000,
        eval_duration=4_000_000,
        total_duration=8_000_000,
    )

    assert extractor.extract_content(payload) == '{"tool":"write_file","args":{"path":"out.txt","content":"ok"}}'
    assert extractor.extract_tool_calls(payload) == []
    assert extractor.extract_usage(payload) == (5, 7, 12)
    assert extractor.extract_timings(payload, latency_ms=99) == (3.0, 4.0, 8.0)
