from __future__ import annotations

import inspect

import pytest

from orket.adapters.llm.local_model_provider import LocalModelProvider
from orket.application.services.local_model_factory import create_local_model_provider

pytestmark = pytest.mark.unit


def test_local_model_provider_timeout_semantics_are_documented_and_validated() -> None:
    """Layer: unit. Verifies provider timeout configuration rejects impossible ordering."""
    doc = inspect.getdoc(LocalModelProvider.__init__) or ""

    assert "total response generation timeout in seconds" in doc
    assert "TCP connection establishment timeout in seconds" in doc
    with pytest.raises(ValueError, match="timeout must be greater than or equal"):
        create_local_model_provider(model="dummy", timeout=10, connect_timeout_seconds=30)
