from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from scripts.common.rerun_diff_ledger import _payload_digest
from scripts.odr.context_continuity_live_metrics import (
    accepted_decision_summaries,
    invariant_summaries,
    latest_architect_delta,
    rejected_path_summaries,
    unresolved_issue_summaries,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_V1_STATE_CONTRACT_PATH = (
    REPO_ROOT
    / "docs"
    / "projects"
    / "archive"
    / "ContextContinuity"
    / "CC03212026"
    / "odr_context_continuity_v1_state_contract.json"
)
ACTIVE_ITEM_STATES = ("accepted", "unresolved", "rejected")
TRACKED_ITEM_CATEGORIES = ("accepted_decision", "unresolved_issue", "rejected_path", "invariant")


def load_v1_state_contract(path: Path | None = None) -> dict[str, Any]:
    contract_path = (path or DEFAULT_V1_STATE_CONTRACT_PATH).resolve()
    payload = json.loads(contract_path.read_text(encoding="utf-8"))
    if str(payload.get("schema_version") or "").strip() != "odr.context_continuity.v1_state_contract.v1":
        raise ValueError("Unsupported V1 state contract schema_version.")
    return payload


def normalize_identity_text(text: str) -> str:
    value = str(text or "").strip()
    while value[:2] in {"- ", "* "}:
        value = value[2:].lstrip()
    value = " ".join(value.replace("\r\n", "\n").replace("\r", "\n").split())
    return value.casefold().rstrip(" .;:!?")


def _item_id(*, category: str, text: str) -> str:
    digest = hashlib.sha256(f"{category}|{normalize_identity_text(text)}".encode("utf-8")).hexdigest()
    return f"cci:{digest[:16]}"


def _artifact_ids(source_inputs: list[dict[str, Any]], artifact_kind: str) -> list[str]:
    return [
        str(item.get("artifact_id") or "").strip()
        for item in source_inputs
        if str(item.get("artifact_kind") or "").strip() == artifact_kind and str(item.get("artifact_id") or "").strip()
    ]


def _explicit_texts(source_inputs: list[dict[str, Any]], artifact_kind: str) -> list[str]:
    rows: list[str] = []
    for item in source_inputs:
        if str(item.get("artifact_kind") or "").strip() != artifact_kind:
            continue
        body = str(item.get("content") or item.get("artifact_body") or "").strip()
        if body:
            rows.append(body)
    return rows


def _fallback_requirement_clauses(requirement: str) -> list[str]:
    rows: list[str] = []
    for chunk in str(requirement or "").replace("\r", "\n").replace("\n", " ").split("."):
        text = chunk.strip()
        if not text:
            continue
        rows.append(text if text[-1] in ".!?" else f"{text}.")
    return rows


def _register_item(
    bucket: dict[str, dict[str, Any]],
    *,
    category: str,
    state: str,
    text: str,
    round_index: int,
    source_input_refs: list[str],
) -> None:
    normalized = normalize_identity_text(text)
    if not normalized:
        return
    key = f"{category}|{normalized}"
    row = bucket.get(key)
    if row is None:
        bucket[key] = {
            "item_id": _item_id(category=category, text=text),
            "category": category,
            "state": state,
            "text": str(text).strip(),
            "identity_evidence": "exact_normalized_text_match",
            "introduced_round": int(round_index),
            "last_confirmed_round": int(round_index),
            "source_input_refs": sorted(set(source_input_refs)),
        }
        return
    row["last_confirmed_round"] = int(round_index)
    row["source_input_refs"] = sorted(set([*list(row.get("source_input_refs") or []), *source_input_refs]))


def _seed_current_items(
    *,
    source_inputs: list[dict[str, Any]],
    current_requirement: str,
    latest_trace: dict[str, Any] | None,
    round_index: int,
) -> dict[str, dict[str, Any]]:
    items: dict[str, dict[str, Any]] = {}
    requirement_ids = _artifact_ids(source_inputs, "current_canonical_artifact")
    accepted_ids = _artifact_ids(source_inputs, "accepted_decision_summary")
    unresolved_ids = _artifact_ids(source_inputs, "unresolved_issue_summary") + _artifact_ids(
        source_inputs, "latest_auditor_critique"
    )
    rejected_ids = _artifact_ids(source_inputs, "rejected_path_summary")
    invariant_ids = _artifact_ids(source_inputs, "invariant_summary") + requirement_ids

    accepted_texts = accepted_decision_summaries(current_requirement)
    if not accepted_texts:
        accepted_texts = _fallback_requirement_clauses(current_requirement)
    for text in [*accepted_texts, *_explicit_texts(source_inputs, "accepted_decision_summary")]:
        _register_item(
            items,
            category="accepted_decision",
            state="accepted",
            text=text,
            round_index=round_index,
            source_input_refs=[*requirement_ids, *accepted_ids],
        )
    for text in [*rejected_path_summaries(current_requirement), *_explicit_texts(source_inputs, "rejected_path_summary")]:
        _register_item(
            items,
            category="rejected_path",
            state="rejected",
            text=text,
            round_index=round_index,
            source_input_refs=rejected_ids,
        )
    unresolved_texts = [
        *unresolved_issue_summaries(scenario_input={"A0": []}, latest_trace=latest_trace),
        *_explicit_texts(source_inputs, "unresolved_issue_summary"),
    ]
    for text in unresolved_texts:
        _register_item(
            items,
            category="unresolved_issue",
            state="unresolved",
            text=text,
            round_index=round_index,
            source_input_refs=unresolved_ids,
        )
    if not latest_trace:
        for text in _explicit_texts(source_inputs, "latest_auditor_critique"):
            _register_item(
                items,
                category="unresolved_issue",
                state="unresolved",
                text=text,
                round_index=round_index,
                source_input_refs=unresolved_ids,
            )
    for text in [
        *invariant_summaries(current_requirement),
        *_explicit_texts(source_inputs, "invariant_summary"),
    ]:
        _register_item(
            items,
            category="invariant",
            state="accepted",
            text=text,
            round_index=round_index,
            source_input_refs=invariant_ids,
        )
    return items


def _active_items_from_prior(prior_payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    if not isinstance(prior_payload, dict):
        return rows
    for state_key in ACTIVE_ITEM_STATES:
        for item in list(prior_payload.get(f"{state_key}_items") or []):
            normalized = normalize_identity_text(str(item.get("text") or ""))
            category = str(item.get("category") or "").strip()
            if not normalized or category not in TRACKED_ITEM_CATEGORIES:
                continue
            rows[f"{category}|{normalized}"] = dict(item)
    for item in list(prior_payload.get("invariants") or []):
        normalized = normalize_identity_text(str(item.get("text") or ""))
        if normalized:
            rows[f"invariant|{normalized}"] = dict(item)
    return rows


def build_v1_shared_state(
    *,
    source_inputs: list[dict[str, Any]],
    current_requirement: str,
    round_index: int,
    artifact_id: str,
    latest_trace: dict[str, Any] | None = None,
    prior_state_payload: dict[str, Any] | None = None,
    contract_path: Path | None = None,
) -> dict[str, Any]:
    contract = load_v1_state_contract(contract_path)
    current_items = _seed_current_items(
        source_inputs=source_inputs,
        current_requirement=current_requirement,
        latest_trace=latest_trace,
        round_index=round_index,
    )
    prior_items = _active_items_from_prior(prior_state_payload)
    reopened_events: list[dict[str, Any]] = []
    regression_events: list[dict[str, Any]] = []
    contradiction_events: list[dict[str, Any]] = []

    accepted_items: list[dict[str, Any]] = []
    unresolved_items: list[dict[str, Any]] = []
    rejected_items: list[dict[str, Any]] = []
    invariants: list[dict[str, Any]] = []

    for key, item in prior_items.items():
        prior_state = str(item.get("state") or "").strip()
        current_item = current_items.pop(key, None)
        normalized_text = normalize_identity_text(str(item.get("text") or ""))
        if current_item is None:
            reopened_item = current_items.pop(f"unresolved_issue|{normalized_text}", None)
            if prior_state == "accepted" and reopened_item is not None:
                reopened_events.append(
                    {
                        "prior_item_id": str(item["item_id"]),
                        "event": "accepted_item_reappeared_as_unresolved",
                        "round_index": int(round_index),
                    }
                )
                regression_events.append(
                    {
                        "prior_item_id": str(item["item_id"]),
                        "event": "accepted_item_weakened_to_unresolved_without_supersession",
                        "round_index": int(round_index),
                    }
                )
                item["last_confirmed_round"] = int(round_index)
                item["source_input_refs"] = sorted(
                    set([*list(item.get("source_input_refs") or []), *list(reopened_item.get("source_input_refs") or [])])
                )
                accepted_items.append(item)
                continue
            if prior_state == "accepted":
                regression_events.append(
                    {
                        "prior_item_id": str(item["item_id"]),
                        "event": "accepted_item_omitted_without_supersession",
                        "round_index": int(round_index),
                    }
                )
                item["last_confirmed_round"] = int(round_index)
                if str(item.get("category") or "") == "invariant":
                    contradiction_events.append(
                        {
                            "prior_item_id": str(item["item_id"]),
                            "event": "invariant_omitted_without_supersession",
                            "round_index": int(round_index),
                        }
                    )
            if prior_state == "accepted":
                accepted_items.append(item)
            elif prior_state == "unresolved":
                unresolved_items.append(item)
            elif prior_state == "rejected":
                rejected_items.append(item)
            continue

        current_state = str(current_item.get("state") or "").strip()
        item["last_confirmed_round"] = int(round_index)
        item["source_input_refs"] = sorted(
            set([*list(item.get("source_input_refs") or []), *list(current_item.get("source_input_refs") or [])])
        )
        if prior_state == "accepted" and current_state == "unresolved":
            reopened_events.append(
                {
                    "prior_item_id": str(item["item_id"]),
                    "event": "accepted_item_reappeared_as_unresolved",
                    "round_index": int(round_index),
                }
            )
            accepted_items.append(item)
            continue
        if prior_state == "rejected" and current_state == "accepted":
            contradiction_events.append(
                {
                    "prior_item_id": str(item["item_id"]),
                    "event": "rejected_path_reintroduced_without_governed_sequence",
                    "round_index": int(round_index),
                }
            )
            rejected_items.append(item)
            continue
        item["state"] = current_state
        if current_state == "accepted":
            accepted_items.append(item)
        elif current_state == "unresolved":
            unresolved_items.append(item)
        elif current_state == "rejected":
            rejected_items.append(item)

    for item in current_items.values():
        state = str(item["state"])
        if state == "accepted":
            accepted_items.append(item)
        elif state == "unresolved":
            unresolved_items.append(item)
        elif state == "rejected":
            rejected_items.append(item)

    for row in accepted_items:
        if str(row.get("category") or "") == "invariant":
            invariants.append(row)
    accepted_non_invariants = [row for row in accepted_items if str(row.get("category") or "") != "invariant"]

    contradiction_count = int((latest_trace or {}).get("contradiction_count") or 0)
    for offset in range(contradiction_count):
        contradiction_events.append(
            {
                "prior_item_id": str(accepted_non_invariants[offset % len(accepted_non_invariants)]["item_id"])
                if accepted_non_invariants
                else None,
                "event": "trace_reported_contradiction",
                "round_index": int(round_index),
            }
        )

    latest_auditor_delta = " | ".join(_explicit_texts(source_inputs, "latest_auditor_critique")[:2])
    payload = {
        "schema_version": "odr.context_continuity.v1_shared_state.v1",
        "round_index": int(round_index),
        "current_canonical_artifact": current_requirement,
        "accepted_items": accepted_non_invariants,
        "unresolved_items": unresolved_items,
        "rejected_items": rejected_items,
        "superseded_items": [],
        "invariants": invariants,
        "latest_architect_delta": latest_architect_delta(latest_trace),
        "latest_auditor_delta": latest_auditor_delta,
        "causal_summary": (
            f"Round {int(round_index)} compiled shared state from {len(source_inputs)} source inputs with "
            f"{len(accepted_non_invariants)} accepted, {len(unresolved_items)} unresolved, and {len(rejected_items)} rejected items."
        ),
        "transition_events": {
            "reopened": reopened_events,
            "contradictions": contradiction_events,
            "regressions": regression_events,
            "supersessions": [],
        },
    }
    return {
        "artifact_id": artifact_id,
        "artifact_kind": "compiled_shared_state",
        "payload": payload,
        "source_history_refs": [
            str(item.get("artifact_id") or "").strip()
            for item in source_inputs
            if str(item.get("artifact_id") or "").strip()
        ],
        "builder_contract_path": str((contract_path or DEFAULT_V1_STATE_CONTRACT_PATH).resolve()),
        "builder_contract_sha256": _payload_digest(contract),
    }


def build_v1_role_view(
    shared_state_artifact: dict[str, Any],
    *,
    role: str,
    role_focus: str,
    contract_path: Path | None = None,
) -> dict[str, str]:
    contract = load_v1_state_contract(contract_path)
    payload = dict(shared_state_artifact.get("artifact_body") or shared_state_artifact.get("payload") or {})

    def _lines(key: str) -> list[str]:
        return [f"- {row['text']}" for row in list(payload.get(key) or []) if str(row.get("text") or "").strip()]

    sections = [
        "### SHARED STATE",
        "#### Current Artifact",
        str(payload.get("current_canonical_artifact") or "(none)"),
        "#### Accepted Decisions",
        *(_lines("accepted_items") or ["- none"]),
        "#### Rejected Paths",
        *(_lines("rejected_items") or ["- none"]),
        "#### Open Issues",
        *(_lines("unresolved_items") or ["- none"]),
        "#### Invariants",
        *(_lines("invariants") or ["- none"]),
        "#### Latest Architect Delta",
        str(payload.get("latest_architect_delta") or "(none)"),
        "#### Latest Auditor Delta",
        str(payload.get("latest_auditor_delta") or "(none)"),
        "#### Causal Summary",
        str(payload.get("causal_summary") or "(none)"),
    ]
    projection = "\n".join(sections)
    focus = role_focus.strip() or str(((contract.get("loader_policy") or {}).get("role_focus_by_role") or {}).get(role) or "")
    loaded_context = projection
    if focus:
        loaded_context = f"{projection}\n\n#### Role Focus\n{focus}"
    return {
        "projection_text": projection,
        "loaded_context": loaded_context,
        "delivery_mode": str(((contract.get("loader_policy") or {}).get("delivery_mode") or "")),
        "loader_contract_path": str((contract_path or DEFAULT_V1_STATE_CONTRACT_PATH).resolve()),
        "loader_contract_sha256": _payload_digest(contract),
        "shared_state_sha256": str(shared_state_artifact.get("artifact_sha256") or ""),
    }


def compute_v1_continuity_run_metrics(state_snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    reopened = 0
    contradictions = 0
    regressions = 0
    accepted_before_final: set[str] = set()
    final_accepted: set[str] = set()
    for index, snapshot in enumerate(state_snapshots):
        payload = dict(snapshot.get("artifact_body") or snapshot.get("payload") or {})
        events = dict(payload.get("transition_events") or {})
        reopened += len(list(events.get("reopened") or []))
        contradictions += len(list(events.get("contradictions") or []))
        regressions += len(list(events.get("regressions") or []))
        accepted_ids = {str(row.get("item_id") or "") for row in list(payload.get("accepted_items") or []) if str(row.get("item_id") or "")}
        if index < len(state_snapshots) - 1:
            accepted_before_final.update(accepted_ids)
        else:
            final_accepted = accepted_ids
    preserved = sum(1 for item_id in accepted_before_final if item_id in final_accepted)
    carry_forward_integrity = 1.0 if not accepted_before_final else preserved / len(accepted_before_final)
    return {
        "reopened_decision_count": reopened,
        "contradiction_count": contradictions,
        "regression_count": regressions,
        "carry_forward_integrity": round(carry_forward_integrity, 6),
    }
