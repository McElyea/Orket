"""Layer: contract. Canonical operation records bind the submitted call and local result."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from orket.application.workflows.turn_artifact_writer import (
    OperationRecordValidationError,
    TurnArtifactWriter,
    build_operation_record,
    validate_operation_record,
)
from orket.core.contracts.protocol_hashing import ProtocolCanonicalizationError, hash_canonical_json

pytestmark = pytest.mark.contract
_OPERATION_ID = "operation-a"
_TOOL = "write_file"
_ARGS = {"path": "agent_output/a.txt", "content": "payload"}
_RESULT = {"ok": True, "touched_paths": ["agent_output/a.txt"]}


def _record() -> dict:
    return build_operation_record(
        operation_id=_OPERATION_ID,
        tool_name=_TOOL,
        tool_args=_ARGS,
        result=_RESULT,
    )


def _validate(record, *, args=None):
    return validate_operation_record(
        record,
        operation_id=_OPERATION_ID,
        tool_name=_TOOL,
        tool_args=_ARGS if args is None else args,
    )


def test_operation_record_digest_matches_published_canonical_hash() -> None:
    """Layer: contract. Canonical .104 result digests remain byte-for-byte compatible."""
    writer = TurnArtifactWriter(Path("unused-operation-record-root"))
    record = _record()

    assert record["result_digest"] == writer.hash_payload(_RESULT)
    assert record["result_digest"] == hash_canonical_json(_RESULT)
    assert _validate(record) == _RESULT


def test_operation_record_uses_persisted_json_equivalence() -> None:
    """Layer: contract. Key order and tuple/list normalization retain one JSON call identity."""
    args = {"nested": {"b": 2, "a": 1}, "values": (1, 2)}
    result = {"ok": True, "values": (3, 4)}
    record = build_operation_record(
        operation_id=_OPERATION_ID,
        tool_name=_TOOL,
        tool_args=args,
        result=result,
    )
    persisted = json.loads(json.dumps(record))
    expected_args = {"values": [1, 2], "nested": {"a": 1, "b": 2}}

    assert _validate(persisted, args=expected_args) == {"ok": True, "values": [3, 4]}


def test_operation_record_distinguishes_json_boolean_from_number() -> None:
    """Layer: contract. Canonical comparison avoids Python's True-equals-one alias."""
    record = build_operation_record(
        operation_id=_OPERATION_ID,
        tool_name=_TOOL,
        tool_args={"value": True},
        result=_RESULT,
    )

    with pytest.raises(OperationRecordValidationError) as raised:
        _validate(record, args={"value": 1})

    assert raised.value.reason == "args_mismatch"
    assert "E_OPERATION_ARTIFACT_INVALID:args_mismatch" in str(raised.value)
    assert "arguments do not match" in str(raised.value)


def _invalid_record(case: str):
    record = deepcopy(_record())
    if case == "operation-id":
        record["operation_id"] = "operation-b"
    elif case == "tool":
        record["tool"] = "read_file"
    elif case == "args":
        record["args"] = {"path": "agent_output/b.txt", "content": "payload"}
    elif case == "noncanonical-args":
        record["args"] = {"value": float("nan")}
    elif case == "noncanonical-result":
        record["result"] = {"ok": True, "value": float("nan")}
    elif case == "result":
        record["result"] = {"ok": False}
    elif case == "digest":
        record["result_digest"] = "0" * 64
    elif case == "missing-digest":
        record.pop("result_digest")
    elif case == "malformed-digest":
        record["result_digest"] = 7
    elif case == "short-digest":
        record["result_digest"] = "abcd"
    elif case == "nonhex-digest":
        record["result_digest"] = "g" * 64
    elif case == "uppercase-digest":
        record["result_digest"] = "A" * 64
    elif case == "malformed-result":
        record["result"] = []
    elif case == "nonobject":
        return []
    return record


@pytest.mark.parametrize(
    ("case", "reason", "fragment"),
    [
        ("operation-id", "operation_id_mismatch", "does not match requested operation"),
        ("tool", "tool_mismatch", "does not match submitted tool"),
        ("args", "args_mismatch", "arguments do not match submitted arguments"),
        ("noncanonical-args", "args_mismatch", "arguments do not match submitted arguments"),
        ("noncanonical-result", "malformed", "result is not canonical JSON"),
        ("result", "result_digest_mismatch", "digest does not match result"),
        ("digest", "result_digest_mismatch", "digest does not match result"),
        ("missing-digest", "malformed", "digest is malformed"),
        ("malformed-digest", "malformed", "digest is malformed"),
        ("short-digest", "malformed", "digest is malformed"),
        ("nonhex-digest", "malformed", "digest is malformed"),
        ("uppercase-digest", "malformed", "digest is malformed"),
        ("malformed-result", "malformed", "result is malformed"),
        ("nonobject", "malformed", "record is malformed"),
    ],
)
def test_operation_record_refusals_have_stable_reason_and_detail(case, reason, fragment) -> None:
    """Layer: contract. One validator supplies machine reason and retained descriptive text."""
    with pytest.raises(OperationRecordValidationError) as raised:
        _validate(_invalid_record(case))

    assert raised.value.reason == reason
    assert f"E_OPERATION_ARTIFACT_INVALID:{reason}" in str(raised.value)
    assert fragment in str(raised.value)


@pytest.mark.parametrize(
    ("args", "result"),
    [
        ({"value": float("nan")}, _RESULT),
        (_ARGS, {"ok": True, "value": float("nan")}),
    ],
    ids=["noncanonical-args", "noncanonical-result"],
)
def test_operation_record_builder_refuses_noncanonical_payloads(args, result) -> None:
    """Layer: contract. New operation truth cannot use the old repr fallback."""
    with pytest.raises(ProtocolCanonicalizationError):
        build_operation_record(
            operation_id=_OPERATION_ID,
            tool_name=_TOOL,
            tool_args=args,
            result=result,
        )


def test_matching_result_and_digest_documents_local_consistency_ceiling() -> None:
    """Layer: contract. A coordinated result+digest rewrite remains locally self-consistent."""
    record = _record()
    rewritten_result = {"ok": True, "source": "coordinated-rewrite"}
    record["result"] = rewritten_result
    record["result_digest"] = hash_canonical_json(rewritten_result)

    assert _validate(record) == rewritten_result
