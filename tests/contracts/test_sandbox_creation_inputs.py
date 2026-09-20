"""Contract proof that core sandbox construction consumes an explicit timestamp."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from orket.core.domain.sandbox import Sandbox, TechStack

pytestmark = pytest.mark.contract


def _payload() -> dict:
    return dict(id='sandbox', rock_id='rock', project_name='Captured',
                tech_stack=TechStack.FASTAPI_REACT_POSTGRES,
                ports=dict(api=18001, frontend=13001, database=15433),
                compose_project='orket-sandbox-captured', workspace_path='captured-workspace',
                api_url='http://localhost:18001', frontend_url='http://localhost:13001',
                database_url='postgresql://localhost:15433/appdb')


def test_core_requires_creation_timestamp() -> None:
    with pytest.raises(ValidationError, match='created_at'):
        Sandbox.model_validate(_payload())


@pytest.mark.parametrize('timestamp', ['2026-09-20T12:34:56+00:00', '2026-09-20T12:34:56.123456+00:00'])
def test_explicit_timestamp_preserves_value_parity(timestamp: str) -> None:
    admitted = dict(_payload(), created_at=timestamp)
    first, second = Sandbox.model_validate(admitted), Sandbox.model_validate(admitted)
    assert first.model_dump() == second.model_dump()
    assert first.created_at == timestamp
