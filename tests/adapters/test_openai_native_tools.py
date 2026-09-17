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


@pytest.mark.parametrize("mode", ["native", "json_wrapper"])
# Layer: unit
def test_profile_selected_transport_preserves_declared_native_surface_or_uses_json(mode):
    """Layer: unit. Explicit profile selection uses its resolved mode without widening the native surface."""
    tools = [{"type": "function", "function": {"name": "write_file", "parameters": {"type": "object"}}}]
    context = {"tool_transport_policy": "profile", "native_tools": tools,
               "native_tool_choice": "required", "native_payload_overrides": {"reasoning_effort": "none"}}
    result = build_openai_native_tooling(model="test-model", runtime_context=context, tool_call_mode=mode)
    assert result == ((tools, "required", {"reasoning_effort": "none"}) if mode == "native" else ([], None, {}))
    assert context["native_tools"] == tools


@pytest.mark.parametrize("mode", [None, "unknown", "unsupported"])
# Layer: unit
def test_profile_selected_transport_refuses_missing_or_unknown_mode(mode):
    """Layer: unit. A missing profile contract cannot turn into an implicit tooling choice."""
    with pytest.raises(ValueError, match="E_TOOL_TRANSPORT_PROFILE_MODE_REQUIRED"):
        build_openai_native_tooling(model="test-model", runtime_context={"tool_transport_policy": "profile"}, tool_call_mode=mode)


# Layer: unit
def test_explicit_native_request_is_not_silently_changed_by_profile_metadata():
    """Layer: unit. Existing explicit native callers retain refusal/dispatch semantics at their provider boundary."""
    tools = [{"type": "function", "function": {"name": "write_file"}}]
    assert build_openai_native_tooling(model="test-model", runtime_context={"native_tools": tools},
                                      tool_call_mode="json_wrapper") == (tools, None, {})


# Layer: unit
def test_unknown_transport_policy_fails_closed():
    """Layer: unit. An unrecognized caller policy does not silently select native or JSON tooling."""
    with pytest.raises(ValueError, match="E_TOOL_TRANSPORT_POLICY_INVALID"):
        build_openai_native_tooling(model="test-model", runtime_context={"tool_transport_policy": "unknown"}, tool_call_mode="native")


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
