from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.odr.context_continuity_live_metrics import unresolved_issue_summaries
from scripts.odr.context_continuity_v1_state import build_v1_role_view, build_v1_shared_state


def initial_unresolved_source_inputs(*, scenario_input: dict[str, Any], round_number: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, issue in enumerate(unresolved_issue_summaries(scenario_input=scenario_input, latest_trace=None)[:3], start=1):
        rows.append(
            {
                "artifact_id": f"initial_unresolved_{idx}_r{round_number}",
                "artifact_kind": "unresolved_issue_summary",
                "authority_level": "authoritative",
                "content": issue,
            }
        )
    return rows


def build_v1_pre_round_state(
    *,
    source_inputs: list[dict[str, Any]],
    current_requirement: str,
    round_number: int,
    prior_state_payload: dict[str, Any] | None,
    latest_trace: dict[str, Any] | None,
    v1_state_contract_path: Path,
    architect_focus: str,
    auditor_focus: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    shared_state = build_v1_shared_state(
        source_inputs=source_inputs,
        current_requirement=current_requirement,
        round_index=round_number - 1,
        artifact_id=f"v1_state_r{round_number}",
        latest_trace=latest_trace,
        prior_state_payload=prior_state_payload,
        contract_path=v1_state_contract_path,
    )
    shared_state_artifact = {
        "artifact_id": str(shared_state["artifact_id"]),
        "artifact_kind": "shared_state_snapshot",
        "artifact_body": dict(shared_state["payload"]),
        "artifact_sha256": "",
    }
    architect_view = build_v1_role_view(
        shared_state_artifact,
        role="architect",
        role_focus=architect_focus,
        contract_path=v1_state_contract_path,
    )
    auditor_view = build_v1_role_view(
        shared_state_artifact,
        role="auditor",
        role_focus=auditor_focus,
        contract_path=v1_state_contract_path,
    )
    return shared_state, {
        "architect": architect_view,
        "auditor": auditor_view,
    }


def build_v1_post_round_state(
    *,
    source_inputs: list[dict[str, Any]],
    current_requirement: str,
    round_number: int,
    prior_state_payload: dict[str, Any] | None,
    latest_trace: dict[str, Any] | None,
    v1_state_contract_path: Path,
) -> dict[str, Any]:
    return build_v1_shared_state(
        source_inputs=source_inputs,
        current_requirement=current_requirement,
        round_index=round_number,
        artifact_id=f"v1_state_post_r{round_number}",
        latest_trace=latest_trace,
        prior_state_payload=prior_state_payload,
        contract_path=v1_state_contract_path,
    )
