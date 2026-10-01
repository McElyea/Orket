"""Explicit fixture inputs with real application model-selection behavior."""
import json

from orket.application.services.model_selection_service import ModelSelectionService, PreparedModelSelection
from orket.core.contracts.model_selection import ModelCompliancePolicy, ModelSelectionSnapshot
from orket.decision_nodes.builtins import DefaultPromptStrategyNode


def prepared_model_selection(strategy=None):
    return PreparedModelSelection(ModelSelectionSnapshot((), (), (), "", ModelCompliancePolicy()),
                                  strategy if strategy is not None else DefaultPromptStrategyNode())


def seed_model_role_catalog(monkeypatch, reader, root, roles):
    """Give the selected API reader real team-role inputs in the fixture root."""
    catalog = root / "model/core/teams/fixture.json"
    catalog.parent.mkdir(parents=True, exist_ok=True)
    catalog.write_text(json.dumps({"roles": {role: {} for role in roles}}), encoding="utf-8")
    monkeypatch.setattr(reader, "project_root", root)


class ModelSelectionFixture:
    def __init__(self, *, environment=None, preferences=None, user_settings=None):
        self.service = ModelSelectionService(environment=environment or {})
        self.preferences = preferences or {}
        self.user_settings = user_settings or {}

    async def prepare(self, organization=None):
        return await self.service.prepare(organization, self.preferences, self.user_settings)
