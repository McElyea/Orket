"""Pure acceptance comparison over application-validated evidence inputs."""
from __future__ import annotations

from collections import Counter

from orket.core.contracts.card_completion import (
    AcceptanceObservation,
    AcceptanceRequirement,
    CardAcceptanceEvidence,
    CardAcceptancePlan,
    CardCompletionDecision,
    CompletionEvidenceSnapshot,
    CompletionScope,
    CompletionState,
)


def evaluate_card_completion(
    *, plan: CardAcceptancePlan | None, scope: CompletionScope | None, snapshot: CompletionEvidenceSnapshot
) -> CardCompletionDecision:
    """No file, provider or storage access; callers own input authenticity.

    A matching class never implies broader coverage. Each observation must match
    one explicitly admitted criterion, verifier, plan and immutable input scope.
    """
    diagnostics = list(snapshot.diagnostics)
    if plan is None:
        diagnostics.append("acceptance_plan_missing")
    if scope is None:
        diagnostics.append("completion_scope_missing")
    if not snapshot.inventory_complete:
        diagnostics.append("evidence_inventory_incomplete")
    if plan is not None and scope is not None and plan.workload_id != scope.workload_id:
        diagnostics.append("acceptance_workload_mismatch")
    satisfied: set[str] = set()
    failed = False
    if plan is not None and scope is not None:
        satisfied, failed, record_diagnostics = _compare_records(plan, scope, snapshot.records)
        diagnostics.extend(record_diagnostics)
    missing = tuple(row.criterion_id for row in plan.requirements if row.criterion_id not in satisfied) if plan else ()
    state = CompletionState.SATISFIED
    if plan is None or scope is None:
        state = CompletionState.NOT_EVALUATED
    elif diagnostics or missing:
        state = CompletionState.FAILED if failed else CompletionState.INSUFFICIENT
    return CardCompletionDecision(
        state=state, scope=scope,
        acceptance_ref=plan.acceptance_ref if plan else None,
        plan_digest=plan.digest if plan else None,
        policy_ref=plan.policy_ref if plan else None,
        missing_criteria=missing, diagnostics=tuple(diagnostics),
        evidence_refs=tuple(row.evidence_ref for row in snapshot.records),
    )


def _compare_records(
    plan: CardAcceptancePlan, scope: CompletionScope, records: tuple[CardAcceptanceEvidence, ...]
) -> tuple[set[str], bool, list[str]]:
    requirements = {row.criterion_id: row for row in plan.requirements}
    counts = Counter(row.criterion_id for row in records)
    refs = Counter(row.evidence_ref for row in records)
    satisfied: set[str] = set()
    diagnostics: list[str] = []
    failed = False
    for row in records:
        problems = _record_diagnostics(row, requirements.get(row.criterion_id), plan.digest, scope)
        if counts[row.criterion_id] != 1:
            problems.append("duplicate_criterion_evidence")
        if refs[row.evidence_ref] != 1:
            problems.append("duplicate_evidence_reference")
        diagnostics.extend(f"{row.criterion_id}:{problem}" for problem in problems)
        if problems:
            continue
        if row.observation == AcceptanceObservation.PASSED:
            satisfied.add(row.criterion_id)
        elif row.observation == AcceptanceObservation.FAILED:
            failed = True
            diagnostics.append(f"{row.criterion_id}:accepted_check_failed")
        else:
            diagnostics.append(f"{row.criterion_id}:accepted_check_not_evaluated")
    for criterion_id in requirements:
        if criterion_id not in counts:
            diagnostics.append(f"{criterion_id}:evidence_missing")
    return satisfied, failed, diagnostics


def _record_diagnostics(
    row: CardAcceptanceEvidence, requirement: AcceptanceRequirement | None, plan_digest: str, scope: CompletionScope
) -> list[str]:
    problems: list[str] = []
    if requirement is None:
        problems.append("undeclared_criterion")
    if row.plan_digest != plan_digest:
        problems.append("acceptance_plan_mismatch")
    if row.scope != scope:
        problems.append("completion_scope_mismatch")
    if row.source != "runtime_verifier":
        problems.append("evidence_source_not_admitted")
    if requirement is not None:
        if (row.verifier_ref, row.verifier_digest) != (requirement.verifier_ref, requirement.verifier_digest):
            problems.append("verifier_mismatch")
        if row.evidence_class != requirement.evidence_class:
            problems.append("evidence_class_mismatch")
    return problems
