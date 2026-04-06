from __future__ import annotations

import importlib

import pytest

from orket.core.domain.execution import ExecutionTurn
from orket.schema import WaitReason

pytestmark = pytest.mark.unit


def test_legacy_domain_execution_module_aliases_to_core_domain() -> None:
    with pytest.deprecated_call():
        module = importlib.import_module("orket.domain.execution")
    assert module.ExecutionTurn is ExecutionTurn


def test_legacy_domain_state_machine_alias_keeps_wait_reason() -> None:
    module = importlib.import_module("orket.domain.state_machine")
    assert module.WaitReason is WaitReason
