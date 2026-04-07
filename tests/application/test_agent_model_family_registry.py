from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from orket.agents import agent as agent_module
from orket.agents.agent import Agent
from orket.agents.model_family_registry import ModelFamilyRegistry
from orket.application.services.control_plane_authority_service import ControlPlaneAuthorityService
from orket.core.domain import ResidualUncertaintyClassification
from orket.core.domain.execution import ToolCallErrorClass
from orket.exceptions import AgentConfigurationError


class _Provider:
    def __init__(self, model: str) -> None:
        self.model = model

    async def complete(
        self,
        messages: list[dict[str, str]],
        runtime_context: dict[str, Any] | None = None,
    ) -> str:
        return ""


class _PartialProvider:
    model = "unknown-7b"

    async def complete(
        self,
        messages: list[dict[str, str]],
        runtime_context: dict[str, Any] | None = None,
    ) -> str:
        return (
            '```json\n'
            '{"tool":"write_file","args":{"path":"agent_output/main.py","content":"print(1)\\n"}}\n'
            '{"tool":"add_issue_comment","args":{"comment":"fallback"}\n'
            '```'
        )


class _MissingConfigLoader:
    dialects: list[str] = []

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def load_asset(self, category: str, name: str, _schema: Any) -> Any:
        if category == "dialects":
            self.dialects.append(name)
        raise FileNotFoundError(name)


def test_model_family_registry_loads_operator_patterns_from_env(monkeypatch) -> None:
    """Layer: unit. Verifies model family registry can be extended without Agent code changes."""
    monkeypatch.setenv("ORKET_MODEL_FAMILY_PATTERNS", '[{"pattern": "mistral", "family": "mistral"}]')

    match = ModelFamilyRegistry.from_config().resolve("mistral-7b-instruct")

    assert match.recognized is True
    assert match.family == "mistral"


def test_agent_logs_unrecognized_model_family(monkeypatch, tmp_path: Path) -> None:
    """Layer: unit. Verifies unknown model families fall back truthfully to generic."""
    events: list[tuple[str, dict[str, Any], dict[str, Any]]] = []

    def _capture(event: str, data: dict[str, Any], **kwargs: Any) -> None:
        events.append((event, data, kwargs))

    monkeypatch.delenv("ORKET_MODEL_FAMILY_PATTERNS", raising=False)
    monkeypatch.setattr(agent_module, "ConfigLoader", _MissingConfigLoader)
    monkeypatch.setattr(agent_module, "log_event", _capture)

    Agent("coder", "description", {}, _Provider("unknown-7b"), config_root=tmp_path, strict_config=False)

    assert any(
        event == "model_family_unrecognized"
        and data == {"agent": "coder", "model": "unknown-7b", "family": "generic"}
        and kwargs.get("level") == "warn"
        for event, data, kwargs in events
    )


@pytest.mark.asyncio
async def test_agent_partial_parse_failure_returns_structured_turn_without_recovery_tool(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Layer: unit. Verifies Agent.run does not execute a hardcoded partial-parse recovery tool."""
    monkeypatch.setattr(agent_module, "ConfigLoader", _MissingConfigLoader)
    calls: list[tuple[str, dict[str, Any]]] = []

    async def _tool(args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        calls.append(("add_issue_comment", args))
        return {"ok": True}

    agent = Agent(
        "coder",
        "description",
        {"add_issue_comment": _tool},
        _PartialProvider(),
        config_root=tmp_path,
        strict_config=False,
    )

    turn = await agent.run(
        {"description": "do work"},
        {"issue_id": "ISSUE-1"},
        tmp_path,
    )

    assert turn.partial_parse_failure is True
    assert turn.error_class is ToolCallErrorClass.PARSE_PARTIAL
    assert turn.tool_calls == []
    assert calls == []


@pytest.mark.asyncio
async def test_agent_run_records_optional_effect_journal_entry(monkeypatch, tmp_path: Path) -> None:
    """Layer: integration. Verifies legacy Agent.run can emit a structured effect journal record when configured."""
    monkeypatch.setattr(agent_module, "ConfigLoader", _MissingConfigLoader)

    class _ToolProvider:
        model = "unknown-7b"

        async def complete(
            self,
            messages: list[dict[str, str]],
            runtime_context: dict[str, Any] | None = None,
        ) -> str:
            return '{"tool":"write_file","args":{"path":"a.txt","content":"hello"}}'

    async def _tool(args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "path": args["path"]}

    agent = Agent(
        "coder",
        "description",
        {"write_file": _tool},
        _ToolProvider(),
        config_root=tmp_path,
        strict_config=False,
        journal=ControlPlaneAuthorityService(),
    )

    turn = await agent.run(
        {"description": "do work"},
        {
            "issue_id": "ISSUE-1",
            "run_id": "run-1",
            "attempt_id": "attempt-1",
            "step_id": "step-1",
            "journal_publication_timestamp": "2026-04-07T00:00:00+00:00",
        },
        tmp_path,
    )

    entries = turn.raw["effect_journal_entries"]
    assert len(entries) == 1
    assert entries[0]["run_id"] == "run-1"
    assert entries[0]["attempt_id"] == "attempt-1"
    assert entries[0]["step_id"] == "step-1:0000"
    assert entries[0]["uncertainty_classification"] == ResidualUncertaintyClassification.NONE.value


def test_agent_strict_config_fails_closed_on_missing_role(monkeypatch, tmp_path: Path) -> None:
    """Layer: unit. Verifies strict agent config does not silently fall back to bare descriptions."""
    monkeypatch.setattr(agent_module, "ConfigLoader", _MissingConfigLoader)

    with pytest.raises(AgentConfigurationError, match="agent role asset load failed"):
        Agent("coder", "description", {}, _Provider("unknown-7b"), config_root=tmp_path)
