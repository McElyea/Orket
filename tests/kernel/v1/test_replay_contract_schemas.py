from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_replay_bundle_schema_requires_turn_paths() -> None:
    schema = _load("docs/projects/OS/contracts/replay-bundle.schema.json")
    validator = Draft202012Validator(schema)

    valid_bundle = {
        "contract_version": "replay_bundle/v1",
        "run_envelope": {
            "run_id": "run-1000",
            "workflow_id": "wf-1000",
            "kernel_contract_version": "kernel_api/v1",
            "schema_version": "v1"
        },
        "registry_digest": "0" * 64,
        "digests": {
            "policy_digest": "1" * 64,
            "runtime_digest": "2" * 64,
            "registry_digest": "0" * 64
        },
        "turn_results": [
            {
                "turn_id": "turn-0001",
                "turn_result_digest": "3" * 64,
                "paths": ["workspace/replay/run-1000/turn-0001.json"]
            }
        ]
    }
    validator.validate(valid_bundle)

    invalid_bundle = deepcopy(valid_bundle)
    invalid_bundle["turn_results"][0]["paths"] = []
    errors = sorted(validator.iter_errors(invalid_bundle), key=lambda err: err.path)
    assert errors, "Expected schema validation failure when turn_result paths are empty."


def test_replay_report_schema_accepts_structured_mismatch_and_nullable_digests() -> None:
    schema = _load("docs/projects/OS/contracts/replay-report.schema.json")
    validator = Draft202012Validator(schema)

    report = {
        "contract_version": "kernel_api/v1",
        "mode": "compare_runs",
        "outcome": "FAIL",
        "status": "DIVERGENT",
        "exit_code": "E_REPLAY_EQUIVALENCE_FAILED",
        "report_id": None,
        "runs_compared": 2,
        "turns_compared": 1,
        "issues": [],
        "events": [],
        "digests": {
            "registry_digest": None,
            "policy_digest": None,
            "runtime_digest": None
        },
        "mismatches_detail": [
            {
                "turn_id": "turn-0001",
                "stage_name": "replay",
                "stage_index": 9,
                "ordinal": 0,
                "surface": "schema",
                "path": "/run_descriptor/contract_version",
                "expected_digest": None,
                "actual_digest": None,
                "diagnostic": None
            }
        ],
        "parity": {
            "kind": "structural_parity",
            "matches": 0,
            "mismatches": 1,
            "expected": {"run_id": "run-a", "turn_digests": []},
            "actual": {"run_id": "run-b", "turn_digests": []}
        }
    }
    validator.validate(report)
