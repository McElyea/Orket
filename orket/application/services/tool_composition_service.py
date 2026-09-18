"""Application-owned executable bindings; strategies select known tool names only."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from orket.core.contracts.decision_inputs import ToolSelectionInput


def compose_default_tool_map(toolbox: Any) -> dict[str, Callable[..., Any]]:
    return {
        "read_file": toolbox.fs.read_file,
        "write_file": toolbox.fs.write_file,
        "create_directory": toolbox.fs.create_directory,
        "list_directory": toolbox.fs.list_directory,
        "image_analyze": toolbox.vision.image_analyze,
        "image_generate": toolbox.vision.image_generate,
        "create_issue": toolbox.cards.create_issue,
        "update_issue_status": toolbox.cards.update_issue_status,
        "add_issue_comment": toolbox.cards.add_issue_comment,
        "get_issue_context": toolbox.cards.get_issue_context,
        "nominate_card": toolbox.governance.nominate_card,
        "report_credits": toolbox.governance.report_credits,
        "refinement_proposal": toolbox.governance.refinement_proposal,
        "request_excuse": toolbox.governance.request_excuse,
        "archive_eval": toolbox.academy.archive_eval,
        "promote_prompt": toolbox.academy.promote_prompt,
        "reforger_inspect": toolbox.reforger.inspect,
        "reforger_run": toolbox.reforger.run,
    }


def select_tool_bindings(toolbox: Any, strategy: Any) -> dict[str, Callable[..., Any]]:
    known = compose_default_tool_map(toolbox)
    selected = strategy.select_tools(ToolSelectionInput(tuple(known)))
    if not isinstance(selected, tuple) or any(not isinstance(name, str) or name not in known for name in selected):
        raise ValueError("Tool strategy must select a tuple of application-owned tool names.")
    if len(selected) != len(set(selected)):
        raise ValueError("Tool strategy selected duplicate tool names.")
    return {name: known[name] for name in selected}
