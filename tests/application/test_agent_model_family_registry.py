from __future__ import annotations

from pathlib import Path
from typing import Any

from orket.agents import agent as agent_module
from orket.agents.agent import Agent
from orket.agents.model_family_registry import ModelFamilyRegistry


class _Provider:
    def __init__(self, model: str) -> None:
        self.model = model

    async def complete(
        self,
        messages: list[dict[str, str]],
        runtime_context: dict[str, Any] | None = None,
    ) -> str:
        return ""


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

    Agent("coder", "description", {}, _Provider("unknown-7b"), config_root=tmp_path)

    assert any(
        event == "model_family_unrecognized"
        and data == {"agent": "coder", "model": "unknown-7b", "family": "generic"}
        and kwargs.get("level") == "warn"
        for event, data, kwargs in events
    )
