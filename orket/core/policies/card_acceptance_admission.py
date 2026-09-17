"""Model proposals cannot declare the criteria that authorize card completion."""
from __future__ import annotations


class ModelAcceptanceDefinitionRejected(ValueError):
    code = "E_CARD_ACCEPTANCE_MODEL_DEFINITION_FORBIDDEN"

    def __init__(self) -> None:
        super().__init__(self.code)


def validate_model_card_payload(payload: object) -> None:
    """Reject reserved definitions before a model proposal reaches asset/storage writes."""
    pending = [payload]
    visited: set[int] = set()
    while pending:
        value = pending.pop()
        if not isinstance(value, (dict, list)) or id(value) in visited:
            continue
        visited.add(id(value))
        if isinstance(value, dict):
            if "completion_acceptance" in value:
                raise ModelAcceptanceDefinitionRejected()
            pending.extend(value.values())
        else:
            pending.extend(value)
