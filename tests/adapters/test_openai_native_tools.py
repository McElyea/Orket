from __future__ import annotations

import logging

import pytest

from orket.adapters.llm.openai_native_tools import _normalized_tools, build_openai_native_tooling

pytestmark = pytest.mark.unit


def test_normalized_tools_warns_when_required_scope_is_empty(caplog: pytest.LogCaptureFixture) -> None:
    """Layer: unit. Verifies missing tool authority is visible instead of silently falling back to no tools."""
    caplog.set_level(logging.WARNING, logger="orket.adapters.llm.openai_native_tools")

    assert _normalized_tools({"verification_scope": {}}) == []
    assert any(record.message == "openai_native_tools_empty_tool_scope" for record in caplog.records)


def test_build_openai_native_tooling_warns_on_empty_gemma_tool_scope(caplog: pytest.LogCaptureFixture) -> None:
    """Layer: unit. Verifies Gemma native tooling records the empty-tool fallback path."""
    caplog.set_level(logging.WARNING, logger="orket.adapters.llm.openai_native_tools")

    tools, tool_choice, overrides = build_openai_native_tooling(
        model="google/gemma-4-26b-a4b",
        runtime_context={"verification_scope": {}},
    )

    assert tools == []
    assert tool_choice is None
    assert overrides == {}
    assert any(record.message == "openai_native_tools_empty_tool_scope" for record in caplog.records)

