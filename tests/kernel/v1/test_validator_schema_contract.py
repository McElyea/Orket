from __future__ import annotations

import json
import tempfile
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from orket.kernel.v1.validator import (
    authorize_tool_call_v1,
    compare_runs_v1,
    execute_turn_v1,
    finish_run_v1,
    replay_run_v1,
    resolve_capability_v1,
    start_run_v1,
)


def _load_schema(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _build_registry(root_schema: dict) -> Registry:
    schema_paths = [
        "docs/projects/OS/contracts/kernel-api-v1.schema.json",
        "docs/projects/OS/contracts/turn-result.schema.json",
        "docs/projects/OS/contracts/kernel-issue.schema.json",
        "docs/projects/OS/contracts/replay-report.schema.json",
        "docs/projects/OS/contracts/capability-decision.schema.json",
    ]
    registry = Registry().with_resource(
        root_schema["$id"],
        Resource.from_contents(root_schema),
    )
    for path in schema_paths:
        schema = _load_schema(path)
        schema_id = schema.get("$id")
        if isinstance(schema_id, str) and schema_id:
            registry = registry.with_resource(schema_id, Resource.from_contents(schema))
    return registry


def test_start_run_v1_response_conforms_to_kernel_api_schema() -> None:
    kernel_api = _load_schema("docs/projects/OS/contracts/kernel-api-v1.schema.json")
    registry = _build_registry(kernel_api)
    response_schema = {"$ref": f"{kernel_api['$id']}#/$defs/StartRunResponse"}

    response = start_run_v1(
        {
            "contract_version": "kernel_api/v1",
            "workflow_id": "wf-schema-start",
            "visibility_mode": "local_only",
            "workspace_root": ".tmp_schema_start",
        }
    )
    Draft202012Validator(response_schema, registry=registry).validate(response)


def test_execute_turn_v1_response_conforms_to_turn_result_schema() -> None:
    turn_result_schema = _load_schema("docs/projects/OS/contracts/turn-result.schema.json")
    registry = _build_registry(turn_result_schema)

    with tempfile.TemporaryDirectory(prefix="orket_validator_schema_") as tmp:
        response = execute_turn_v1(
            {
                "contract_version": "kernel_api/v1",
                "run_handle": {
                    "contract_version": "kernel_api/v1",
                    "run_id": "run-schema-turn",
                    "visibility_mode": "local_only",
                    "workspace_root": str(Path(tmp)),
                },
                "turn_id": "turn-0001",
                "commit_intent": "stage_and_request_promotion",
                "turn_input": {
                    "stage_triplet": {
                        "stem": "data/dto/schema/turn",
                        "body": {"dto_type": "invocation", "id": "inv:schema"},
                        "links": {"declares": {"type": "skill", "id": "skill:schema", "relationship": "declares"}},
                        "manifest": {},
                    }
                },
            }
        )
    Draft202012Validator(turn_result_schema, registry=registry).validate(response)


def test_finish_run_v1_response_conforms_to_kernel_api_schema() -> None:
    kernel_api = _load_schema("docs/projects/OS/contracts/kernel-api-v1.schema.json")
    registry = _build_registry(kernel_api)
    response_schema = {"$ref": f"{kernel_api['$id']}#/$defs/FinishRunResponse"}

    response = finish_run_v1(
        {
            "contract_version": "kernel_api/v1",
            "run_handle": {
                "contract_version": "kernel_api/v1",
                "run_id": "run-schema-finish",
                "visibility_mode": "local_only",
            },
            "outcome": "PASS",
        }
    )
    Draft202012Validator(response_schema, registry=registry).validate(response)


def test_replay_run_v1_response_conforms_to_replay_report_schema() -> None:
    replay_report_schema = _load_schema("docs/projects/OS/contracts/replay-report.schema.json")
    registry = _build_registry(replay_report_schema)

    response = replay_run_v1(
        {
            "contract_version": "kernel_api/v1",
            "run_descriptor": {
                "run_id": "run-schema-replay",
                "workflow_id": "wf-schema-replay",
                "policy_profile_ref": "policy:v1",
                "model_profile_ref": "model:v1",
                "runtime_profile_ref": "runtime:v1",
                "trace_ref": "trace://run-schema-replay",
                "state_ref": "state://run-schema-replay",
                "contract_version": "kernel_api/v1",
                "schema_version": "v1",
            },
        }
    )
    Draft202012Validator(replay_report_schema, registry=registry).validate(response)


def test_compare_runs_v1_response_conforms_to_replay_report_schema() -> None:
    replay_report_schema = _load_schema("docs/projects/OS/contracts/replay-report.schema.json")
    registry = _build_registry(replay_report_schema)

    response = compare_runs_v1(
        {
            "contract_version": "kernel_api/v1",
            "run_a": {"run_id": "run-a", "turn_digests": []},
            "run_b": {"run_id": "run-b", "turn_digests": []},
            "compare_mode": "structural_parity",
        }
    )
    Draft202012Validator(replay_report_schema, registry=registry).validate(response)


def test_authorize_tool_call_v1_response_conforms_to_kernel_api_schema() -> None:
    kernel_api = _load_schema("docs/projects/OS/contracts/kernel-api-v1.schema.json")
    registry = _build_registry(kernel_api)
    response_schema = {"$ref": f"{kernel_api['$id']}#/$defs/AuthorizeToolCallResponse"}

    response = authorize_tool_call_v1(
        {
            "contract_version": "kernel_api/v1",
            "context": {"subject": "agent:schema", "capability_enforcement": True},
            "tool_request": {"action": "tool.call", "resource": "tool://schema"},
        }
    )
    Draft202012Validator(response_schema, registry=registry).validate(response)


def test_resolve_capability_v1_response_conforms_to_kernel_api_schema() -> None:
    kernel_api = _load_schema("docs/projects/OS/contracts/kernel-api-v1.schema.json")
    registry = _build_registry(kernel_api)
    response_schema = {"$ref": f"{kernel_api['$id']}#/$defs/ResolveCapabilityResponse"}

    response = resolve_capability_v1(
        {
            "contract_version": "kernel_api/v1",
            "role": "coder",
            "task": "schema",
            "context": {"capability_enforcement": False},
        }
    )
    Draft202012Validator(response_schema, registry=registry).validate(response)
