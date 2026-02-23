from __future__ import annotations

import json
import tempfile
from pathlib import Path

from jsonschema import Draft202012Validator, RefResolver

from orket.kernel.v1.validator import execute_turn_v1, finish_run_v1, start_run_v1


def _load_schema(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _build_resolver(root_schema: dict) -> RefResolver:
    schema_paths = [
        "docs/projects/OS/contracts/kernel-api-v1.schema.json",
        "docs/projects/OS/contracts/turn-result.schema.json",
        "docs/projects/OS/contracts/kernel-issue.schema.json",
        "docs/projects/OS/contracts/replay-report.schema.json",
        "docs/projects/OS/contracts/capability-decision.schema.json",
    ]
    store: dict[str, dict] = {}
    for path in schema_paths:
        schema = _load_schema(path)
        schema_id = schema.get("$id")
        if isinstance(schema_id, str) and schema_id:
            store[schema_id] = schema
    return RefResolver.from_schema(root_schema, store=store)


def test_start_run_v1_response_conforms_to_kernel_api_schema() -> None:
    kernel_api = _load_schema("docs/projects/OS/contracts/kernel-api-v1.schema.json")
    resolver = _build_resolver(kernel_api)
    response_schema = kernel_api["$defs"]["StartRunResponse"]

    response = start_run_v1(
        {
            "contract_version": "kernel_api/v1",
            "workflow_id": "wf-schema-start",
            "visibility_mode": "local_only",
            "workspace_root": ".tmp_schema_start",
        }
    )
    Draft202012Validator(response_schema, resolver=resolver).validate(response)


def test_execute_turn_v1_response_conforms_to_turn_result_schema() -> None:
    turn_result_schema = _load_schema("docs/projects/OS/contracts/turn-result.schema.json")
    resolver = _build_resolver(turn_result_schema)

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
    Draft202012Validator(turn_result_schema, resolver=resolver).validate(response)


def test_finish_run_v1_response_conforms_to_kernel_api_schema() -> None:
    kernel_api = _load_schema("docs/projects/OS/contracts/kernel-api-v1.schema.json")
    resolver = _build_resolver(kernel_api)
    response_schema = kernel_api["$defs"]["FinishRunResponse"]

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
    Draft202012Validator(response_schema, resolver=resolver).validate(response)

