from __future__ import annotations

from typing import Any

PACKET2_KEY = "truthful_runtime_packet2"
PACKET2_SCHEMA_VERSION = "1.0"
_FINAL_DISPOSITIONS = {"accepted_with_repair", "no_repair"}


def build_packet2_extension(*, artifacts: dict[str, Any]) -> dict[str, Any] | None:
    facts = _collect_packet2_facts(artifacts)
    if not facts:
        return None

    entries = _normalize_repair_entries(facts.get("repair_entries"))
    if not entries:
        return None

    final_disposition = str(facts.get("final_disposition") or "accepted_with_repair").strip()
    if final_disposition not in _FINAL_DISPOSITIONS:
        raise ValueError("packet2_final_disposition_invalid")

    return {
        "schema_version": PACKET2_SCHEMA_VERSION,
        "repair_ledger": {
            "repair_occurred": True,
            "repair_count": len(entries),
            "final_disposition": final_disposition,
            "entries": entries,
        },
    }


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
    return normalized


def _collect_packet2_facts(artifacts: dict[str, Any]) -> dict[str, Any]:
    return normalize_packet2_facts(artifacts.get("packet2_facts"))


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
        merged_reasons = _normalize_reasons(list(existing.get("reasons") or []) + reasons)
        existing["reasons"] = merged_reasons
        existing["material_change"] = bool(existing.get("material_change", True) or entry["material_change"])
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
