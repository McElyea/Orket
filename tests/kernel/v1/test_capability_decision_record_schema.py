from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator


def _schema() -> dict:
    return json.loads(
        Path("docs/projects/OS/contracts/capability-decision-record.schema.json").read_text(encoding="utf-8")
    )


def _base_record() -> dict:
    return {
        "contract_version": "kernel_api/v1",
        "decision_id": "dec-0001",
        "run_id": "run-0001",
        "turn_id": "turn-0001",
        "tool_name": "shell_command",
        "action": "tool.call",
        "ordinal": 0,
        "outcome": "allowed",
        "stage": "capability",
        "deny_code": None,
        "info_code": None,
        "reason": "Policy granted tool call.",
        "provenance": {"policy_ref": "policy://kernel/default", "policy_version": "v1"},
    }


def test_schema_accepts_allowed_denied_skipped_and_unresolved() -> None:
    validator = Draft202012Validator(_schema())

    allowed = _base_record()
    validator.validate(allowed)

    denied = _base_record()
    denied.update(
        {
            "decision_id": "dec-0002",
            "outcome": "denied",
            "deny_code": "E_CAPABILITY_DENIED",
            "info_code": None,
            "provenance": None,
            "reason": "Policy denied tool call.",
        }
    )
    validator.validate(denied)

    skipped = _base_record()
    skipped.update(
        {
            "decision_id": "dec-0003",
            "outcome": "skipped",
            "deny_code": None,
            "info_code": "I_CAPABILITY_SKIPPED",
            "provenance": None,
            "reason": "Capability enforcement is disabled.",
        }
    )
    validator.validate(skipped)

    unresolved = _base_record()
    unresolved.update(
        {
            "decision_id": "dec-0004",
            "outcome": "unresolved",
            "deny_code": "E_CAPABILITY_NOT_RESOLVED",
            "info_code": None,
            "provenance": None,
            "reason": "Capability context could not be resolved.",
        }
    )
    validator.validate(unresolved)


def test_schema_rejects_skipped_without_skipped_info_code() -> None:
    validator = Draft202012Validator(_schema())
    invalid = deepcopy(_base_record())
    invalid.update(
        {
            "outcome": "skipped",
            "info_code": "I_GATEKEEPER_PASS",
            "provenance": None,
            "reason": "Capability skipped.",
        }
    )
    errors = sorted(validator.iter_errors(invalid), key=lambda err: err.path)
    assert errors, "Expected schema validation failure for invalid skipped info_code."
