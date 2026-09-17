"""Project application acceptance into prompts without granting storage permission."""
from __future__ import annotations

import json
from typing import Any

from orket.core.contracts.card_completion import CardCompletionDecision, CompletionEvidenceSnapshot
from orket.core.contracts.card_completion_commit import CardCompletionContext
from orket.core.policies.card_completion import evaluate_card_completion


def card_completion_prompt_payload(context: dict[str, Any]) -> dict[str, Any]:
    decision = context.get("card_completion_decision")
    if not isinstance(decision, CardCompletionDecision):
        decision = evaluate_card_completion(
            plan=None, scope=None, snapshot=CompletionEvidenceSnapshot(diagnostics=("completion_authority_missing",)),
        )
    bound = context.get("card_completion_context")
    definition = (json.loads(bound.workload_inputs_json)["params"]["completion_acceptance"]
                  if isinstance(bound, CardCompletionContext) else None)
    return {**decision.model_dump(mode="json"), "criteria_definition": definition,
            "completion_rule": "Successful completion requires the declared acceptance checks. "
                               "Report blocked when acceptance is unavailable or fails."}


def guard_review_contract_lines(context: dict[str, Any], required_statuses: list[str]) -> list[str]:
    acceptance = card_completion_prompt_payload(context)
    lines = [
        "Guard Rejection Contract:" if "blocked" in required_statuses else "Guard Decision Contract:",
        "- Support checks alone cannot authorize successful completion.",
        f"- Declared acceptance state: {acceptance['state']}.",
        "- Choose done only when declared acceptance is acceptance_satisfied and no concrete defect is present.",
        "- If acceptance is missing, insufficient or failed, report its missing criteria and diagnostics; "
        "choose blocked when it is an allowed status.",
    ]
    if "blocked" in required_statuses:
        lines.extend([
            "- If you set update_issue_status.status to blocked, put guard_review inside that call's args.",
            '- Required payload schema: {"rationale":"...", "violations":[...], "remediation_actions":[...]}.',
            "- rationale must be non-empty.",
            "- violations must contain at least one concrete defect.",
            "- remediation_actions must contain at least one concrete action.",
        ])
    else:
        lines.append("- Do not invent an allowed blocked status or claim completion when acceptance is unavailable.")
    return lines
