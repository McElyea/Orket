"""Contract: declared prompt-context reads must stay inside invocation capture.

This structural guard covers literal context.get calls in the named renderers.
It is not a dynamic call-graph or runtime mutation proof.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from orket.application.services import card_completion_prompt
from orket.application.workflows import turn_message_builder, turn_path_resolver
from orket.application.workflows.turn_message_inputs import _PROMPT_CONTEXT_KEYS
from orket.runtime.config import compact_turn_packet, turn_prompt_contracts

pytestmark = pytest.mark.contract


def test_captured_keys_cover_declared_prompt_context_reads():
    observed = set()
    for module in (turn_message_builder, turn_path_resolver, card_completion_prompt,
                   compact_turn_packet, turn_prompt_contracts):
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "get" and isinstance(node.func.value, ast.Name)
                    and node.func.value.id in {"context", "runtime_context"}):
                continue
            assert node.args and isinstance(node.args[0], ast.Constant), (
                module.__name__, node.lineno, "Dynamic prompt key needs explicit capture review",
            )
            observed.add(node.args[0].value)
    assert len(_PROMPT_CONTEXT_KEYS) == len(set(_PROMPT_CONTEXT_KEYS))
    assert "available_tools" in observed
    assert "available_tools" not in _PROMPT_CONTEXT_KEYS  # Derived from the captured role tools.
    assert observed - {"available_tools"} <= set(_PROMPT_CONTEXT_KEYS)
