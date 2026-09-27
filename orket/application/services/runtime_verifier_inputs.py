"""Detach a verification invocation before native observation or command admission."""
from __future__ import annotations

from copy import copy, deepcopy
from types import SimpleNamespace
from typing import TYPE_CHECKING

from orket.application.services.process_input_service import capture_process_context

if TYPE_CHECKING:
    from orket.application.services.runtime_verifier import RuntimeVerifier


def capture_verifier_inputs(verifier: RuntimeVerifier) -> RuntimeVerifier:
    # Copy consumed values; the existing supervisor owns every admitted process.
    captured = copy(verifier)
    captured.workspace_root, environment = capture_process_context(
        cwd=verifier.workspace_root, environment=verifier.command_environment,
    )
    captured.command_environment = dict(environment)
    captured.process_supervisor = verifier.process_supervisor.for_workspace(captured.workspace_root)
    rules = getattr(verifier.organization, "process_rules", None)
    captured.organization = SimpleNamespace(process_rules=deepcopy(rules) if isinstance(rules, dict) else {})
    captured.issue_params = deepcopy(verifier.issue_params)
    captured.artifact_contract = deepcopy(verifier.artifact_contract)
    return captured
