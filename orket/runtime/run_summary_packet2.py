from __future__ import annotations

from typing import Any

PACKET2_KEY = "truthful_runtime_packet2"
PACKET2_SCHEMA_VERSION = "1.0"
_FINAL_DISPOSITIONS = {"accepted_with_repair", "no_repair"}
_AUDIT_STATUSES = {"missing", "verified"}
_IDEMPOTENCY_DEDUPE_STATUSES = {"reused", "single_delivery"}
_SOURCE_ATTRIBUTION_MODES = {"optional", "required"}
_SOURCE_ATTRIBUTION_STATUSES = {"blocked", "optional_unverified", "verified"}


def build_packet2_extension(*, artifacts: dict[str, Any]) -> dict[str, Any] | None:
    facts = _collect_packet2_facts(artifacts)
    if not facts:
        return None

    payload: dict[str, Any] = {"schema_version": PACKET2_SCHEMA_VERSION}
    repair_ledger = _build_repair_ledger(facts)
    if repair_ledger is not None:
        payload["repair_ledger"] = repair_ledger

    narration_to_effect_audit = dict(facts.get("narration_to_effect_audit") or {})
    if narration_to_effect_audit:
        payload["narration_to_effect_audit"] = narration_to_effect_audit

    idempotency = dict(facts.get("idempotency") or {})
    if idempotency:
        payload["idempotency"] = idempotency

    source_attribution = dict(facts.get("source_attribution") or {})
    if source_attribution:
        payload["source_attribution"] = source_attribution

    return payload if len(payload) > 1 else None


def normalize_packet2_facts(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, Any] = {}
    entries = _normalize_repair_entries(value.get("repair_entries"))
    if entries:
        normalized["repair_entries"] = entries
    final_disposition = str(value.get("final_disposition") or "").strip()
    if final_disposition:
        normalized["final_disposition"] = final_disposition
    narration_to_effect_audit = _normalize_narration_to_effect_audit(value.get("narration_to_effect_audit"))
    if narration_to_effect_audit:
        normalized["narration_to_effect_audit"] = narration_to_effect_audit
    idempotency = _normalize_idempotency(value.get("idempotency"))
    if idempotency:
        normalized["idempotency"] = idempotency
    source_attribution = _normalize_source_attribution(value.get("source_attribution"))
    if source_attribution:
        normalized["source_attribution"] = source_attribution
    return normalized


def _collect_packet2_facts(artifacts: dict[str, Any]) -> dict[str, Any]:
    return normalize_packet2_facts(artifacts.get("packet2_facts"))


def _build_repair_ledger(facts: dict[str, Any]) -> dict[str, Any] | None:
    entries = _normalize_repair_entries(facts.get("repair_entries"))
    if not entries:
        return None
    final_disposition = str(facts.get("final_disposition") or "accepted_with_repair").strip()
    if final_disposition not in _FINAL_DISPOSITIONS:
        raise ValueError("packet2_final_disposition_invalid")
    return {
        "repair_occurred": True,
        "repair_count": len(entries),
        "final_disposition": final_disposition,
        "entries": entries,
    }


def _normalize_repair_entries(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    deduped: dict[str, dict[str, Any]] = {}
    for item in value:
        if not isinstance(item, dict):
            continue
        repair_id = str(item.get("repair_id") or "").strip()
        if not repair_id:
            continue
        reasons = _normalize_reasons(item.get("reasons"))
        entry = {
            "repair_id": repair_id,
            "turn_index": _normalize_turn_index(item.get("turn_index")),
            "source_event": str(item.get("source_event") or "turn_corrective_reprompt").strip() or "turn_corrective_reprompt",
            "strategy": str(item.get("strategy") or "corrective_reprompt").strip() or "corrective_reprompt",
            "reasons": reasons,
            "material_change": bool(item.get("material_change", True)),
        }
        issue_id = str(item.get("issue_id") or "").strip()
        if issue_id:
            entry["issue_id"] = issue_id
        existing = deduped.get(repair_id)
        if existing is None:
            deduped[repair_id] = entry
            continue
        existing["reasons"] = _normalize_reasons(list(existing.get("reasons") or []) + reasons)
        existing["material_change"] = bool(existing.get("material_change", True) or entry["material_change"])
    return [deduped[key] for key in sorted(deduped)]


def _normalize_narration_to_effect_audit(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    entries = _normalize_narration_entries(value.get("entries"))
    if not entries:
        return {}
    verified_count = sum(1 for row in entries if row["audit_status"] == "verified")
    return {
        "audit_occurred": True,
        "verified_count": verified_count,
        "missing_effect_count": len(entries) - verified_count,
        "entries": entries,
    }


def _normalize_narration_entries(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    deduped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for item in value:
        if not isinstance(item, dict):
            continue
        operation_id = str(item.get("operation_id") or "").strip()
        tool = str(item.get("tool") or "").strip()
        effect_target = str(item.get("effect_target") or "").strip()
        audit_status = str(item.get("audit_status") or "").strip().lower()
        failure_reason = str(item.get("failure_reason") or "").strip().lower()
        if not operation_id or not tool or not effect_target or audit_status not in _AUDIT_STATUSES:
            continue
        entry = {
            "operation_id": operation_id,
            "tool": tool,
            "effect_target": effect_target,
            "audit_status": audit_status,
            "failure_reason": "none" if audit_status == "verified" else failure_reason or "unknown",
        }
        issue_id = str(item.get("issue_id") or "").strip()
        if issue_id:
            entry["issue_id"] = issue_id
        role_name = str(item.get("role_name") or "").strip()
        if role_name:
            entry["role_name"] = role_name
        turn_index = _normalize_turn_index(item.get("turn_index"))
        if turn_index > 0:
            entry["turn_index"] = turn_index
        step_id = str(item.get("step_id") or "").strip()
        if step_id:
            entry["step_id"] = step_id
        deduped[(tool, operation_id, effect_target)] = entry
    return [deduped[key] for key in sorted(deduped)]


def _normalize_idempotency(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    surfaces = _normalize_idempotency_surfaces(value.get("surfaces"))
    if not surfaces:
        return {}
    duplicate_operation_count = sum(1 for row in surfaces if row["dedupe_status"] == "reused")
    return {
        "policy_schema_version": str(value.get("policy_schema_version") or "1.0").strip() or "1.0",
        "observed_surface_count": len(surfaces),
        "duplicate_operation_count": duplicate_operation_count,
        "surfaces": surfaces,
    }


def _normalize_idempotency_surfaces(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for item in value:
        if not isinstance(item, dict):
            continue
        surface = str(item.get("surface") or "").strip()
        operation_id = str(item.get("operation_id") or "").strip()
        tool = str(item.get("tool") or "").strip()
        target = str(item.get("target") or "").strip()
        dedupe_status = str(item.get("dedupe_status") or "").strip().lower()
        if not surface or not operation_id or not tool or not target or dedupe_status not in _IDEMPOTENCY_DEDUPE_STATUSES:
            continue
        entry = {
            "surface": surface,
            "operation_id": operation_id,
            "tool": tool,
            "target": target,
            "dedupe_status": dedupe_status,
            "conflict_action": str(item.get("conflict_action") or "").strip(),
            "replay_allowed": bool(item.get("replay_allowed", False)),
        }
        issue_id = str(item.get("issue_id") or "").strip()
        if issue_id:
            entry["issue_id"] = issue_id
        role_name = str(item.get("role_name") or "").strip()
        if role_name:
            entry["role_name"] = role_name
        turn_index = _normalize_turn_index(item.get("turn_index"))
        if turn_index > 0:
            entry["turn_index"] = turn_index
        deduped[(surface, operation_id)] = entry
    return [deduped[key] for key in sorted(deduped)]


def _normalize_source_attribution(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    mode = str(value.get("mode") or "").strip().lower()
    synthesis_status = str(value.get("synthesis_status") or "").strip().lower()
    if mode not in _SOURCE_ATTRIBUTION_MODES or synthesis_status not in _SOURCE_ATTRIBUTION_STATUSES:
        return {}
    claims = _normalize_source_attribution_claims(value.get("claims"))
    sources = _normalize_source_attribution_sources(value.get("sources"))
    missing_requirements = _normalize_reasons(value.get("missing_requirements"))
    payload: dict[str, Any] = {
        "mode": mode,
        "high_stakes": bool(value.get("high_stakes", False)),
        "synthesis_status": synthesis_status,
        "claim_count": len(claims),
        "source_count": len(sources),
        "missing_requirements": missing_requirements,
        "artifact_provenance_verified": bool(value.get("artifact_provenance_verified", False)),
        "receipt_artifact_path": str(value.get("receipt_artifact_path") or "").strip(),
    }
    if claims:
        payload["claims"] = claims
    if sources:
        payload["sources"] = sources
    receipt_operation_id = str(value.get("receipt_operation_id") or "").strip()
    if receipt_operation_id:
        payload["receipt_operation_id"] = receipt_operation_id
    return payload


def _normalize_source_attribution_claims(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    deduped: dict[str, dict[str, Any]] = {}
    for item in value:
        if not isinstance(item, dict):
            continue
        claim_id = str(item.get("claim_id") or "").strip()
        claim = str(item.get("claim") or "").strip()
        source_ids = _normalize_reasons(item.get("source_ids"))
        if not claim_id or not claim or not source_ids:
            continue
        deduped[claim_id] = {
            "claim_id": claim_id,
            "claim": claim,
            "source_ids": source_ids,
        }
    return [deduped[key] for key in sorted(deduped)]


def _normalize_source_attribution_sources(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    deduped: dict[str, dict[str, Any]] = {}
    for item in value:
        if not isinstance(item, dict):
            continue
        source_id = str(item.get("source_id") or "").strip()
        title = str(item.get("title") or "").strip()
        uri = str(item.get("uri") or "").strip()
        kind = str(item.get("kind") or "").strip()
        if not source_id or not title or not uri or not kind:
            continue
        deduped[source_id] = {
            "source_id": source_id,
            "title": title,
            "uri": uri,
            "kind": kind,
        }
    return [deduped[key] for key in sorted(deduped)]


def _normalize_reasons(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    seen: set[str] = set()
    rows: list[str] = []
    for raw in value:
        token = str(raw or "").strip()
        if not token or token in seen:
            continue
        seen.add(token)
        rows.append(token)
    rows.sort()
    return rows


def _normalize_turn_index(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(0, value)
    raw = str(value or "").strip()
    if not raw:
        return 0
    try:
        return max(0, int(raw))
    except ValueError:
        return 0
