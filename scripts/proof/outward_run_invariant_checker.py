from __future__ import annotations

import hashlib
import json
from typing import Any

from scripts.proof.outward_run_witness_contract import (
    BUNDLE_SCHEMA_VERSION,
    COMPARE_SCOPE,
    INVARIANT_SCHEMA_VERSION,
    OPERATOR_SURFACE,
)
from scripts.proof.outward_run_witness_ledger import verify_committed_artifact, verify_package_ledger
from scripts.proof.outward_run_witness_package import OutwardRunWitnessPackage


_APPROVED_SEQUENCE = [
    "run_submitted",
    "run_started",
    "turn_started",
    "proposal_made",
    "proposal_pending_approval",
    "proposal_approved",
    "tool_invoked",
    "commitment_recorded",
    "turn_completed",
    "run_completed",
]


def evaluate_outward_run_invariants(
    package: OutwardRunWitnessPackage,
    *,
    scope: str = COMPARE_SCOPE,
) -> dict[str, Any]:
    bundle = package.bundle
    events = [event for event in package.ledger_export.get("events") or [] if isinstance(event, dict)]
    failures: list[str] = []
    invariants: list[dict[str, Any]] = []

    def check(invariant_id: str, passed: bool, failure_code: str, detail: str | None = None) -> None:
        invariants.append(
            {
                "id": invariant_id,
                "status": "passed" if passed else "failed",
                "failure_code": None if passed else failure_code,
                "detail": detail,
            }
        )
        if not passed and failure_code not in failures:
            failures.append(failure_code)

    schema_failures = _schema_failures(bundle, scope)
    for code in schema_failures:
        check("schema-gate", False, code)

    positions = _positions(events)
    run_id = str(bundle.get("run_id") or "")
    tool_events = [event for event in events if event.get("event_type") == "tool_invoked"]
    commitment_events = [event for event in events if event.get("event_type") == "commitment_recorded"]
    terminal_events = [event for event in events if event.get("event_type") in {"run_completed", "run_failed"}]
    approved_position = _first_position(events, "proposal_approved")
    tool_position = _first_position(events, "tool_invoked")
    commitment_position = _first_position(events, "commitment_recorded")

    check(
        "ORP-INV-001",
        bool(positions.get("run_submitted")) and all(_position(event) > positions["run_submitted"][0] for event in tool_events),
        "effect_before_admission",
    )
    approval_failure = _approval_authority_failure(bundle)
    check(
        "ORP-INV-002",
        approval_failure == ""
        and approved_position is not None
        and tool_position is not None
        and approved_position < tool_position,
        approval_failure or "effect_before_approval",
    )

    terminal_ok = _terminal_truth_ok(bundle, terminal_events, commitment_events, tool_events)
    check("ORP-INV-003", terminal_ok == "", terminal_ok or "final_truth_missing")

    artifact_result = verify_committed_artifact(package)
    effect_ok = bool(tool_events) and bool(bundle.get("effect_evidence")) and artifact_result.get("result") == "pass"
    check("ORP-INV-004", effect_ok, str(artifact_result.get("failure_code") or "effect_evidence_missing"))

    check("ORP-INV-005", _authority_digests_present(bundle), _authority_digest_failure(bundle))

    ledger_result = verify_package_ledger(package)
    check("ORP-INV-006", ledger_result.get("result") == "pass", str(ledger_result.get("failure_code") or "ledger_chain_broken"))

    tier_ok = str(bundle.get("claim_tier_request") or "outward_lab_only") == "outward_lab_only"
    check("ORP-INV-007", tier_ok, "claim_tier_not_supported")

    pending_position = _first_position(events, "proposal_pending_approval")
    made_position = _first_position(events, "proposal_made")
    check(
        "ORP-INV-008",
        made_position is not None and pending_position is not None and made_position < pending_position,
        "proposal_ordering_violated",
    )
    check("ORP-INV-009", _tool_args_align(bundle, events), "tool_args_digest_drift")
    check(
        "ORP-INV-010",
        tool_position is not None
        and commitment_position is not None
        and tool_position < commitment_position
        and _commitment_matches(bundle, events),
        "commitment_missing_after_effect",
    )
    turn_completed_position = _first_position(events, "turn_completed")
    check(
        "ORP-INV-011",
        commitment_position is not None
        and turn_completed_position is not None
        and commitment_position < turn_completed_position,
        "turn_not_completed_after_commitment",
    )
    check("ORP-INV-012", _model_evidence_anchored(bundle, events), _model_evidence_failure(bundle, events))
    check("ORP-INV-013", not _denied_proposal_invoked(events), "denied_proposal_invoked")
    check("ORP-INV-014", not _policy_rejected_proposal_invoked(events), "policy_rejected_proposal_invoked")
    check("ORP-INV-016", _ledger_positions_monotonic(events), "ledger_sequence_gap")
    check("ORP-INV-022", str(package.ledger_export.get("export_scope") or "") == "all", "full_ledger_export_required")

    failures = list(dict.fromkeys(failures))
    assigned = "outward_lab_only" if not failures else "none"
    signature = _invariant_signature(invariants, failures, scope=scope, claim_tier_assigned=assigned)
    return {
        "schema_version": INVARIANT_SCHEMA_VERSION,
        "result": "pass" if not failures else "fail",
        "claim_tier_assigned": assigned,
        "invariants": invariants,
        "failures": failures,
        "missing_evidence": failures,
        "invariant_signature": signature,
    }


def _schema_failures(bundle: dict[str, Any], scope: str) -> list[str]:
    failures: list[str] = []
    if bundle.get("schema_version") != BUNDLE_SCHEMA_VERSION:
        failures.append("bundle_schema_missing_or_unsupported")
    if bundle.get("compare_scope") != scope:
        failures.append("compare_scope_missing_or_unsupported")
    if bundle.get("operator_surface") != OPERATOR_SURFACE:
        failures.append("operator_surface_missing")
    run_authority = bundle.get("run_authority")
    if not isinstance(run_authority, dict) or not run_authority.get("run_id"):
        failures.append("run_authority_missing")
    elif run_authority.get("run_id") != bundle.get("run_id"):
        failures.append("run_id_drift")
    if isinstance(run_authority, dict):
        policy = bundle.get("policy_identity") if isinstance(bundle.get("policy_identity"), dict) else {}
        run_tool = str(run_authority.get("acceptance_contract_tool") or "")
        required_tools = {str(tool) for tool in policy.get("approval_required_tools") or []}
        if run_tool and run_tool not in required_tools:
            failures.append("policy_tool_not_in_approval_required")
    return failures


def _positions(events: list[dict[str, Any]]) -> dict[str, list[int]]:
    result: dict[str, list[int]] = {}
    for event in events:
        result.setdefault(str(event.get("event_type") or ""), []).append(_position(event))
    return result


def _first_position(events: list[dict[str, Any]], event_type: str) -> int | None:
    values = [_position(event) for event in events if event.get("event_type") == event_type]
    return min(values) if values else None


def _position(event: dict[str, Any]) -> int:
    return int(event.get("position") or 0)


def _terminal_truth_ok(
    bundle: dict[str, Any],
    terminal_events: list[dict[str, Any]],
    commitment_events: list[dict[str, Any]],
    tool_events: list[dict[str, Any]],
) -> str:
    if len(terminal_events) != 1:
        return "final_truth_missing" if not terminal_events else "terminal_status_drift"
    terminal_payload = terminal_events[0].get("payload") if isinstance(terminal_events[0].get("payload"), dict) else {}
    run_authority = bundle.get("run_authority") if isinstance(bundle.get("run_authority"), dict) else {}
    statuses = {
        str(run_authority.get("status") or ""),
        str(run_authority.get("run_status") or ""),
        str(terminal_payload.get("status") or ""),
    }
    if not statuses <= {"completed", "success"}:
        return "terminal_status_drift"
    if str(terminal_payload.get("outcome") or "") not in {"success", "completed"}:
        return "final_truth_missing"
    if tool_events and not commitment_events:
        return "commitment_missing_after_effect"
    return ""


def _authority_digests_present(bundle: dict[str, Any]) -> bool:
    run_authority = bundle.get("run_authority") if isinstance(bundle.get("run_authority"), dict) else {}
    approvals = [item for item in bundle.get("approval_authority") or [] if isinstance(item, dict)]
    ledger = bundle.get("ledger_evidence") if isinstance(bundle.get("ledger_evidence"), dict) else {}
    refs = [item for item in bundle.get("artifact_refs") or [] if isinstance(item, dict)]
    return (
        bool(run_authority.get("run_record_digest"))
        and all(item.get("approval_record_digest") for item in approvals)
        and bool(ledger.get("ledger_export_digest"))
        and any(ref.get("classification") == "authority" and ref.get("digest") for ref in refs)
    )


def _authority_digest_failure(bundle: dict[str, Any]) -> str:
    if bundle.get("projection_only_authority") is True:
        return "projection_substituted_for_authority"
    refs = [item for item in bundle.get("artifact_refs") or [] if isinstance(item, dict)]
    if refs and not any(ref.get("classification") == "authority" for ref in refs):
        return "projection_substituted_for_authority"
    return "missing_authority_digest" if not _authority_digests_present(bundle) else "projection_substituted_for_authority"


def _tool_args_align(bundle: dict[str, Any], events: list[dict[str, Any]]) -> bool:
    approval = _first_dict(bundle.get("approval_authority"))
    effect = _first_dict(bundle.get("effect_evidence"))
    tool_payload = _first_payload(events, "tool_invoked")
    if not approval or not effect or not tool_payload:
        return False
    return (
        approval.get("status") == "approved"
        and approval.get("tool_name") == effect.get("tool_name") == tool_payload.get("connector_name")
        and approval.get("tool_args_digest") == effect.get("tool_args_digest") == tool_payload.get("args_hash")
    )


def _commitment_matches(bundle: dict[str, Any], events: list[dict[str, Any]]) -> bool:
    effect = _first_dict(bundle.get("effect_evidence"))
    commitment = _first_payload(events, "commitment_recorded")
    return bool(commitment) and commitment.get("tool") == effect.get("tool_name") and commitment.get("run_id") == bundle.get("run_id")


def _approval_authority_failure(bundle: dict[str, Any]) -> str:
    approvals = [item for item in bundle.get("approval_authority") or [] if isinstance(item, dict)]
    if not approvals:
        return "approval_authority_missing"
    return "" if any(item.get("status") == "approved" for item in approvals) else "approval_status_not_approved"


def _model_evidence_anchored(bundle: dict[str, Any], events: list[dict[str, Any]]) -> bool:
    model = _first_dict(bundle.get("model_invocation_evidence"))
    proposal = _first_payload(events, "proposal_made")
    if not model or not proposal:
        return False
    pairs = {
        "model_invocation_digest": "model_invocation_sha256",
        "model_prompt_redacted_digest": "model_prompt_redacted_sha256",
        "model_response_redacted_digest": "model_response_content_sha256",
        "proposal_extraction_digest": "proposal_extraction_sha256",
    }
    return all(str(model.get(left) or "") == str(proposal.get(right) or "") for left, right in pairs.items())


def _model_evidence_failure(bundle: dict[str, Any], events: list[dict[str, Any]]) -> str:
    return "model_invocation_digest_drift" if _first_dict(bundle.get("model_invocation_evidence")) and _first_payload(events, "proposal_made") else "model_invocation_evidence_not_anchored"


def _denied_proposal_invoked(events: list[dict[str, Any]]) -> bool:
    denied = _first_position(events, "proposal_denied")
    invoked = _first_position(events, "tool_invoked")
    return denied is not None and invoked is not None and denied < invoked


def _policy_rejected_proposal_invoked(events: list[dict[str, Any]]) -> bool:
    rejected = _first_position(events, "proposal_policy_rejected")
    invoked = _first_position(events, "tool_invoked")
    return rejected is not None and invoked is not None and rejected < invoked


def _ledger_positions_monotonic(events: list[dict[str, Any]]) -> bool:
    positions = [_position(event) for event in events]
    return positions == list(range(1, len(events) + 1))


def _first_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                return item
    return {}


def _first_payload(events: list[dict[str, Any]], event_type: str) -> dict[str, Any]:
    for event in events:
        if event.get("event_type") == event_type and isinstance(event.get("payload"), dict):
            return event["payload"]
    return {}


def _invariant_signature(
    invariants: list[dict[str, Any]],
    failures: list[str],
    *,
    scope: str,
    claim_tier_assigned: str,
) -> str:
    material = {
        "schema_version": INVARIANT_SCHEMA_VERSION,
        "compare_scope": scope,
        "operator_surface": OPERATOR_SURFACE,
        "claim_tier_assigned": claim_tier_assigned,
        "invariants": {str(item["id"]): str(item["status"]) for item in invariants},
        "missing_evidence": sorted(set(failures)),
    }
    encoded = json.dumps(material, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
