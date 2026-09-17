from __future__ import annotations

import importlib

import pytest

from orket.core.domain.execution import ExecutionTurn
from orket.schema import WaitReason

pytestmark = pytest.mark.contract


def test_legacy_domain_execution_module_aliases_to_core_domain() -> None:
    with pytest.deprecated_call():
        module = importlib.import_module("orket.domain.execution")
    assert module.ExecutionTurn is ExecutionTurn


def test_legacy_domain_state_machine_alias_keeps_wait_reason() -> None:
    module = importlib.import_module("orket.domain.state_machine")
    assert module.WaitReason is WaitReason


# Layer: contract
@pytest.mark.parametrize("name", [
    "bug_fix_phase", "critical_path", "failure_reporter", "fixture_verifier", "reconciler",
    "sandbox", "sandbox_verifier", "verification", "verification_runner",
])
def test_existing_domain_module_aliases_retain_canonical_identity(name):
    legacy = importlib.import_module(f"orket.domain.{name}")
    canonical = importlib.import_module(f"orket.core.domain.{name}")
    assert legacy is canonical
    assert getattr(importlib.import_module("orket.domain"), name) is canonical
