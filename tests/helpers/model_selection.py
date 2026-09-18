"""Explicit fixture inputs with real application model-selection behavior."""
from orket.application.services.model_selection_service import ModelSelectionService, PreparedModelSelection
from orket.core.contracts.model_selection import ModelCompliancePolicy, ModelSelectionSnapshot
from orket.decision_nodes.builtins import DefaultPromptStrategyNode


def prepared_model_selection(strategy=None):
    return PreparedModelSelection(ModelSelectionSnapshot((), (), (), "", ModelCompliancePolicy()),
                                  strategy if strategy is not None else DefaultPromptStrategyNode())


class ModelSelectionFixture:
    def __init__(self, *, environment=None, preferences=None, user_settings=None):
        self.service = ModelSelectionService(environment=environment or {})
        self.preferences = preferences or {}
        self.user_settings = user_settings or {}

    async def prepare(self, organization=None):
        return await self.service.prepare(organization, self.preferences, self.user_settings)
