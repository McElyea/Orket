from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from orket.application.services.outward_connector_service import OutwardConnectorService
from orket.application.services.outward_run_execution_plan import current_step_index, model_tool_call
from orket.core.domain.outward_approvals import OutwardApprovalProposal
from orket.core.domain.outward_authorization import OutwardAuthorization, args_hash, canonical_json
from orket.core.domain.outward_runs import OutwardRunRecord


def resolved_policy(run: OutwardRunRecord, context: dict[str, Any]) -> str:
    return canonical_json({
        "connector_policy": context, "run_policy": run.policy_overrides,
        "max_turns": run.max_turns, "acceptance_contract": run.task.get("acceptance_contract", {}),
    })


async def bind_authorization(
    proposal: OutwardApprovalProposal, run: OutwardRunRecord,
    args: dict[str, Any], connectors: OutwardConnectorService,
) -> OutwardAuthorization:
    run, args = deepcopy(run), deepcopy(args)
    context = await connectors.authorization_context(proposal.tool, args)
    policy = resolved_policy(run, context)
    return OutwardAuthorization(
        proposal_id=proposal.proposal_id, run_id=run.run_id, execution_generation=run.execution_generation,
        turn=run.current_turn, step_index=current_step_index(run), namespace=run.namespace,
        workspace_root=context["workspace_root"], target_ref=context["target_ref"],
        tool=proposal.tool, connector_version=context["connector"]["contract_version"],
        arguments_json=canonical_json(args), arguments_digest=args_hash(args),
        policy_json=policy, policy_digest=args_hash(json.loads(policy)),
        submitted_at=proposal.submitted_at, expires_at=proposal.expires_at,
    )


def validate_run_authorization(binding: OutwardAuthorization, run: OutwardRunRecord) -> None:
    if (run.run_id, run.execution_generation, run.current_turn, current_step_index(run), run.namespace) != (
        binding.run_id, binding.execution_generation, binding.turn, binding.step_index, binding.namespace,
    ):
        raise RuntimeError("E_OUTWARD_AUTHORIZATION_SCOPE_DRIFT")
    recorded_call = model_tool_call(run)
    if recorded_call is None or recorded_call["tool"] != binding.tool or args_hash(recorded_call["args"]) != binding.arguments_digest:
        raise RuntimeError("E_OUTWARD_AUTHORIZATION_ARGUMENT_DRIFT")


async def validate_dispatch_authorization(
    binding: OutwardAuthorization, run: OutwardRunRecord, connectors: OutwardConnectorService,
) -> None:
    validate_run_authorization(binding, run)
    context = await connectors.authorization_context(binding.tool, binding.arguments)
    validate_run_authorization(binding, run)
    if resolved_policy(run, context) != binding.policy_json:
        raise RuntimeError("E_OUTWARD_AUTHORIZATION_POLICY_DRIFT")
    if context["workspace_root"] != binding.workspace_root or context["target_ref"] != binding.target_ref:
        raise RuntimeError("E_OUTWARD_AUTHORIZATION_TARGET_DRIFT")
