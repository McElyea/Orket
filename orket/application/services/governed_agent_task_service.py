"""Public SDK submission admission for one bounded, read-only report invocation."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.storage.governed_agent_task_inputs import read_agent_task_json
from orket.application.services.governed_agent_report_verifier import StructuredReportVerifier
from orket.application.services.governed_agent_submission_service import (
    GovernedAgentProviderOptions,
    execute_prepared_governed_agent,
)
from orket.extensions.manager import ExtensionManager
from orket_extension_sdk import AgentIterationRequest, GovernedAgentSubmission, canonical_digest_sha256


async def run_governed_agent_task(
    *, project_root: Path, db_path: Path, catalog_path: Path, submission_path: Path, inputs_path: Path,
    provider: GovernedAgentProviderOptions, environment: Mapping[str, str], run_id: str,
    utc_now: Callable[[], datetime],
) -> dict[str, Any]:
    if not project_root.is_absolute():
        raise ValueError("E_AGENT_TASK_ABSOLUTE_ROOT_REQUIRED")
    paths = tuple(project_root / path for path in (db_path, catalog_path, submission_path, inputs_path))
    if any(not path.is_absolute() for path in paths):
        raise ValueError("E_AGENT_TASK_ABSOLUTE_PATH_REQUIRED")
    db_path, catalog_path, submission_path, inputs_path = paths
    captured_environment = dict(environment)
    submission, launch, inputs = await run_owned_thread(
        lambda: _prepare_task(project_root, catalog_path, submission_path, inputs_path, captured_environment),
        label="governed-agent-task-preparation",
    )
    verifier = StructuredReportVerifier(submission)
    now = _observe_time(utc_now)
    request = build_task_request(submission, inputs, run_id=run_id, now=now)
    return await execute_prepared_governed_agent(
        db_path=db_path, launch=launch, request=request, provider=provider, environment=captured_environment,
        creation_timestamp_utc=now.isoformat(), decision_timestamps_utc=(lambda: _observe_time(utc_now).isoformat(),),
        next_lease_expiries_utc=(), verifier=verifier, admission_payload=submission.to_wire(),
    )


def _prepare_task(root, catalog, submission_path, inputs_path, environment):
    payload = read_agent_task_json(submission_path)
    if not isinstance(payload, dict):
        raise ValueError("E_AGENT_TASK_SUBMISSION_OBJECT_REQUIRED")
    submission = GovernedAgentSubmission.from_wire(payload)
    _admit_report_policy(submission)
    # Reject unsupported verification before catalog import or provider construction.
    StructuredReportVerifier(submission)
    inputs = read_agent_task_json(inputs_path)
    if not isinstance(inputs, list):
        raise ValueError("E_AGENT_TASK_INPUT_ARRAY_REQUIRED")
    manager = ExtensionManager(catalog_path=catalog, project_root=root, invocation_root=root, environment=environment)
    launch = manager.resolve_governed_agent_workload(submission.workload_id)
    if launch.extension_id != submission.extension_id:
        raise ValueError("E_AGENT_TASK_EXTENSION_MISMATCH")
    required = set(launch.required_capabilities)
    if required - set(submission.allowed_capabilities):
        raise ValueError("E_AGENT_TASK_REQUIRED_CAPABILITY_UNADMITTED")
    resources = launch.agent_declaration["resource_requirements"]
    if (submission.iteration_budget.model_calls > resources["max_model_calls_per_iteration"]
            or submission.iteration_budget.output_bytes > resources["max_result_bytes"]
            or launch.agent_declaration["recovery_posture"] != submission.recovery_posture):
        raise ValueError("E_AGENT_TASK_MANIFEST_LIMIT_MISMATCH")
    return submission, launch, inputs


def _admit_report_policy(submission: GovernedAgentSubmission) -> None:
    if (submission.policy_schema_version != "governed_agent_report_policy.v1"
            or submission.allowed_capabilities != ("agent.iteration.v1",)
            or submission.recovery_posture != "fail_closed"):
        raise ValueError("E_AGENT_TASK_POLICY_UNSUPPORTED")
    policy = {"schema_version": submission.policy_schema_version,
              "allowed_capabilities": list(submission.allowed_capabilities),
              "namespace_scope": list(submission.namespace_scope), "recovery_posture": submission.recovery_posture}
    if submission.policy_digest != "sha256:" + canonical_digest_sha256(policy):
        raise ValueError("E_AGENT_TASK_POLICY_DIGEST_MISMATCH")
    for budget in (submission.run_budget, submission.iteration_budget):
        if (budget.iterations != 1 or not 1 <= budget.wall_time_ms <= 3_600_000
                or budget.effect_proposals or budget.per_capability_effects or budget.artifact_bytes
                or budget.total_inference_concurrency != 1):
            raise ValueError("E_AGENT_TASK_REPORT_BUDGET_UNSUPPORTED")
    if submission.run_budget.wall_time_ms != submission.iteration_budget.wall_time_ms:
        raise ValueError("E_AGENT_TASK_REPORT_TIME_LIMIT_MISMATCH")


def build_task_request(submission: GovernedAgentSubmission, inputs: list[dict[str, Any]],
                       *, run_id: str, now: datetime) -> AgentIterationRequest:
    deadline = (now + timedelta(milliseconds=submission.run_budget.wall_time_ms)).isoformat()
    return AgentIterationRequest.from_wire({
        "object_type": "agent_iteration_request", "schema_version": "agent_iteration_request.v1",
        "identity": {"run_id": run_id, "attempt_id": f"agent-attempt:{run_id}:1", "iteration_ordinal": 1,
                     "step_id": f"agent-step:{run_id}:00000001", "trace_id": f"agent-trace:{run_id}:00000001",
                     "invocation_id": f"agent-invocation:{run_id}:00000001", "fencing_generation": 1},
        "objective_ref": submission.objective_ref, "acceptance_ref": submission.acceptance_ref,
        "authoritative_context_refs": list(submission.initial_context_refs), "prior_verified_output_refs": [],
        "materialized_inputs": inputs, "effect_receipts": [],
        "admitted_capabilities": list(submission.allowed_capabilities), "namespace_scope": list(submission.namespace_scope),
        "model_profiles": [profile.to_wire() for profile in submission.requested_model_profiles],
        "policy_ref": submission.policy_ref, "policy_digest": submission.policy_digest,
        "remaining_run_budget": _remaining(submission.run_budget, "run_remaining", run_id),
        "remaining_iteration_budget": _remaining(submission.iteration_budget, "iteration_remaining", run_id),
        "deadline_utc": deadline, "lease_expires_at_utc": deadline,
        "cancellation": {"object_type": "agent_cancellation", "schema_version": "agent_cancellation.v1",
                         "requested": False, "cancellation_epoch": 0, "reason": None},
        "extension_config": {"governed_submission": submission.to_wire()},
    })


def _remaining(budget, scope: str, run_id: str) -> dict[str, Any]:
    payload = budget.model_dump(mode="json", exclude={"snapshot_digest"})
    payload.update(scope=scope, snapshot_ref=f"agent-budget:{run_id}:{scope}:1")
    return {**payload, "snapshot_digest": "sha256:" + canonical_digest_sha256(payload)}


def _observe_time(clock: Callable[[], datetime]) -> datetime:
    value = clock()
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("E_AGENT_TASK_UTC_CLOCK_REQUIRED")
    return value
