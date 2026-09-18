"""Explicit flow inputs shared by real storage and public authoring checks."""
from datetime import UTC, datetime

from orket.application.services.flow_authoring_service import FlowAuthoringService, FlowDefinitionWriteModel
from orket.application.services.runtime_input_service import RuntimeInputService


def definition(name="original"):
    return FlowDefinitionWriteModel.model_validate({
        "name": name, "description": "Captured authoring input",
        "nodes": [{"node_id": "start", "kind": "start", "label": "Start"},
                  {"node_id": "card", "kind": "card", "label": "Card", "assigned_card_id": "CARD"},
                  {"node_id": "final", "kind": "final", "label": "Final"}],
        "edges": [{"edge_id": "a", "from_node_id": "start", "to_node_id": "card"},
                  {"edge_id": "b", "from_node_id": "card", "to_node_id": "final"}],
    })


class FlowInputs(RuntimeInputService):
    def __init__(self):
        self.flow_calls = 0
        self.revision_calls = 0

    def create_flow_id(self):
        self.flow_calls += 1
        return "FLOW-FIXED"

    def create_flow_revision_id(self):
        self.revision_calls += 1
        return f"frv_{self.revision_calls}"

    def utc_now(self):
        return datetime(2026, 9, 18, 12, tzinfo=UTC)


def service(repo, inputs=None):
    inputs = inputs or FlowInputs()
    return FlowAuthoringService(
        flow_repo=repo, now_iso_factory=inputs.utc_now_iso,
        flow_id_factory=inputs.create_flow_id, revision_id_factory=inputs.create_flow_revision_id,
    )
