"""Declared, bounded acceptance for the canonical tiny summation workload."""
from __future__ import annotations

import json
from typing import Any

from orket.core.cards_runtime_contract import (
    APP_EXECUTION_PROFILE,
    ARTIFACT_EXECUTION_PROFILE,
    DEFAULT_APP_PRIMARY_OUTPUT,
    DEFAULT_ARCHITECTURE_PATH,
    DEFAULT_REQUIREMENTS_PATH,
    DEFAULT_SOURCE_ATTRIBUTION_PATH,
)
from orket.core.contracts.card_acceptance_inputs import ArtifactAcceptance, PythonCliAcceptance

SUM_REQUIREMENT = "Program shall sum two integers from CLI args and print result."
SUM_DESIGN_NOTE = "Single class SummationApp with one run(args) method."


def core_acceptance_runtime_contract(issue_id: str, definition: dict[str, Any]) -> dict[str, Any]:
    primary = {
        "REQ-1": DEFAULT_REQUIREMENTS_PATH, "ARC-1": DEFAULT_ARCHITECTURE_PATH,
        "COD-1": DEFAULT_APP_PRIMARY_OUTPUT, "REV-1": DEFAULT_APP_PRIMARY_OUTPUT,
        "EVD-1": DEFAULT_SOURCE_ATTRIBUTION_PATH,
    }[issue_id]
    is_app = issue_id in {"COD-1", "REV-1"}
    read_paths = [DEFAULT_REQUIREMENTS_PATH, DEFAULT_ARCHITECTURE_PATH] if is_app else []
    return {
        "execution_profile": APP_EXECUTION_PROFILE if is_app else ARTIFACT_EXECUTION_PROFILE,
        "artifact_contract": {
            "kind": "app" if is_app else "artifact", "primary_output": primary,
            "required_write_paths": [primary], "required_read_paths": read_paths,
            "review_read_paths": list(definition["artifact_paths"]),
        },
    }


def _artifact_definition(workload_id: str, cases: list[dict[str, Any]]) -> dict[str, Any]:
    return ArtifactAcceptance(
        schema_version="card_artifact_acceptance.v1", acceptance_ref=f"{workload_id}.acceptance.v1",
        policy_ref="tiny-summation-artifacts.v1", workload_id=workload_id,
        artifact_paths=tuple(sorted({case["path"] for case in cases})), cases=tuple(cases),
    ).model_dump(mode="json")


def _sum_definition(workload_id: str) -> dict[str, Any]:
    return PythonCliAcceptance(
        acceptance_ref=f"{workload_id}.acceptance.v1", policy_ref="two-integer-summation.v1", workload_id=workload_id,
        entrypoint="agent_output/main.py",
        artifact_paths=("agent_output/main.py", "agent_output/requirements.txt", "agent_output/design.txt"),
        cases=tuple({"criterion_id": name, "description": description, "arguments": arguments, "expected_json": expected}
                    for name, description, arguments, expected in (
                        ("positive", "Sum two positive integers", ("17", "25"), "42"),
                        ("negative", "Sum integers with opposing signs", ("-5", "2"), "-3"),
                        ("zero", "Sum zeros", ("0", "0"), "0"),
                    )),
    ).model_dump(mode="json")


def core_acceptance_definitions(*, source_attribution_json: str) -> dict[str, dict[str, Any]]:
    requirement = {
        "kind": "text_equals", "criterion_id": "summation-requirement", "description": "Record the declared CLI requirement",
        "path": "agent_output/requirements.txt", "expected_text": SUM_REQUIREMENT,
    }
    design = [{"kind": "json_value_equals", "criterion_id": key, "description": f"Declared design {key}",
               "path": "agent_output/design.txt", "key_path": (key,), "expected_json": json.dumps(value)}
              for key, value in (("recommendation", "monolith"), ("frontend_framework", "vue"), ("notes", SUM_DESIGN_NOTE))]
    return {
        "REQ-1": _artifact_definition("sum-requirements", [requirement]),
        "ARC-1": _artifact_definition("sum-design", [requirement, *design]),
        "COD-1": _sum_definition("sum-implementation"),
        "REV-1": _sum_definition("sum-review"),
        "EVD-1": _artifact_definition("sum-source-receipt", [{
            "kind": "json_value_equals", "criterion_id": "source-receipt", "description": "Declared source attribution receipt",
            "path": "agent_output/source_attribution_receipt.json", "expected_json": source_attribution_json,
        }]),
    }
