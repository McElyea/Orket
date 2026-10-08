"""Shared ticket-example inputs for the packaged demo and its acceptance controls."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from orket_extension_sdk import canonical_json
from orket_extension_sdk.agent_fixtures import agent_iteration_request, agent_model_profile_request, prefixed_digest
from orket_extension_sdk.agent_testing import ticket_report_fixture


def materialized_ticket_input(reference: str, kind: str, content: Any) -> dict[str, Any]:
    encoded = canonical_json(content).encode("utf-8")
    return {"reference": reference, "kind": kind, "media_type": "application/json", "encoding": "json",
            "digest": prefixed_digest(content), "encoded_bytes": len(encoded), "content": content,
            "provenance_refs": [f"provenance:{reference}"]}


def ticket_report_request(case_id: str, *, now: datetime, staged: bool = False) -> dict[str, Any]:
    request = agent_iteration_request()
    fixture = ticket_report_fixture(case_id)
    request["objective_ref"] = "objective:ticket-report" + (f":{case_id}" if case_id != "mixed" else "")
    request["acceptance_ref"] = "acceptance:ticket-report-v1"
    request["authoritative_context_refs"] = list(fixture["batches"])
    request["materialized_inputs"] = [
        materialized_ticket_input(request["objective_ref"], "objective", fixture["objective"]),
        materialized_ticket_input(request["acceptance_ref"], "acceptance", fixture["acceptance"]),
        *[materialized_ticket_input(ref, "authoritative_context", content) for ref, content in fixture["batches"].items()],
    ]
    request["deadline_utc"] = (now + timedelta(seconds=8)).isoformat()
    request["lease_expires_at_utc"] = (now + timedelta(seconds=7)).isoformat()
    request["model_profiles"] = []
    for role in ("planner", "actor", "critic"):
        profile = agent_model_profile_request()
        profile.update(role=role, profile_ref=f"local.{role}")
        request["model_profiles"].append(profile)
    for scope in ("remaining_run_budget", "remaining_iteration_budget"):
        multiplier = 2 if scope == "remaining_run_budget" else 1
        request[scope].update(model_calls=3 * multiplier, input_tokens=12_288 * multiplier,
                              output_tokens=4_096 * multiplier,
                              per_role_model_calls=[{"role": role, "count": multiplier}
                                                    for role in ("planner", "actor", "critic")])
        request[scope]["snapshot_digest"] = prefixed_digest(
            {key: value for key, value in request[scope].items() if key != "snapshot_digest"})
    if staged:
        request["authoritative_context_refs"] = ["artifact:ticket-batch-a"]
        request["materialized_inputs"] = [item for item in request["materialized_inputs"]
                                          if item["reference"] != "artifact:ticket-batch-b"]
    return request


def ticket_continuation_inputs(case_id: str = "mixed") -> dict[str, Any]:
    fixture = ticket_report_fixture(case_id)
    return {"2": [materialized_ticket_input("artifact:ticket-batch-b", "authoritative_context",
                                           fixture["batches"]["artifact:ticket-batch-b"])]}


def live_ticket_report_request(case_id: str, *, now: datetime) -> dict[str, Any]:
    request = ticket_report_request(case_id, now=now, staged=True)
    request["deadline_utc"] = (now + timedelta(minutes=10)).isoformat()
    request["lease_expires_at_utc"] = (now + timedelta(minutes=9)).isoformat()
    for profile in request["model_profiles"]:
        profile.update(max_output_tokens=512, timeout_ms=120_000)
    for scope in ("remaining_run_budget", "remaining_iteration_budget"):
        multiplier = 2 if scope == "remaining_run_budget" else 1
        request[scope].update(model_calls=4 * multiplier, input_tokens=16_384 * multiplier,
                              output_tokens=2_048 * multiplier, repair_attempts=multiplier, wall_time_ms=600_000,
                              per_role_model_calls=[{"role": role, "count": 2 * multiplier}
                                                    for role in ("planner", "actor", "critic")])
        request[scope]["snapshot_digest"] = prefixed_digest(
            {key: value for key, value in request[scope].items() if key != "snapshot_digest"})
    return request
