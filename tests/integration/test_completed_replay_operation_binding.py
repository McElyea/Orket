"""Operation and checkpoint binding controls for completed governed replay."""
from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

import pytest

from orket.adapters.storage.async_file_tools import AsyncFileTools
from tests.helpers.operation_binding import (
    ARGS,
    before_after,
    captured_destination,
    context,
    make_case,
    mutate_record,
    proposal,
    seed_terminal,
    write_operation,
)
from tests.helpers.turn_control_plane_clock import deterministic_turn_clock as deterministic_turn_clock

pytestmark = [pytest.mark.integration, pytest.mark.asyncio, pytest.mark.usefixtures("deterministic_turn_clock")]


def _record(record_property, **payload):  # type: ignore[no-untyped-def]
    record_property("completed_replay_binding_observation", json.dumps(payload, sort_keys=True))


async def _reenter(case):  # type: ignore[no-untyped-def]
    return await case.executor.execute_turn(
        case.issue,
        case.role,
        case.model,
        case.toolbox,
        context(),
        system_prompt="SYSTEM",
    )


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        pytest.param(None, None, id="exact"),
        pytest.param("tool", "tool_mismatch", id="tool"),
        pytest.param("args", "args_mismatch", id="args"),
        pytest.param("operation_id", "operation_id_mismatch", id="operation-id"),
        pytest.param("result", "result_digest_mismatch", id="result-only"),
        pytest.param("digest", "result_digest_mismatch", id="digest-only"),
        pytest.param("missing_digest", "malformed", id="missing-digest"),
        pytest.param("malformed_digest", "malformed", id="malformed-digest"),
        pytest.param("invalid_json", "malformed", id="invalid-json"),
        pytest.param("non_dict", "malformed", id="non-dict"),
    ],
)
# Layer: integration
async def test_completed_replay_requires_bound_operation_record(
    tmp_path: Path, record_property, mutation: str | None, reason: str | None,
) -> None:
    case = make_case(tmp_path, [proposal()])
    seed = await seed_terminal(case, success=True)
    if mutation == "invalid_json":
        await write_operation(case, "{not-json")
    elif mutation == "non_dict":
        await write_operation(case, "[]")
    elif mutation is not None:
        await write_operation(case, mutate_record(seed.operation, mutation))

    result, before_state, after_state, before_files, after_files = await before_after(
        case, lambda: _reenter(case)
    )
    _record(record_property, mutation=mutation, reason=reason, result_success=result.success,
        result_error=result.error, model_calls=case.model.calls, toolbox_calls=case.toolbox.calls,
        before_state=before_state, after_state=after_state,
        before_files=before_files, after_files=after_files)

    if mutation is None:
        assert result.success is True and result.turn is not None
        assert result.turn.note == "control_plane_completed_replay"
        assert result.turn.tool_calls[0].result == seed.operation["result"]
    else:
        assert result.success is False
        assert result.error is not None and f"E_OPERATION_ARTIFACT_INVALID:{reason}" in result.error
    assert case.model.calls == 1 and case.toolbox.calls == 1 and len(case.probe.calls) == 1
    assert after_state == before_state and after_files == before_files


# Layer: integration
async def test_completed_replay_distinguishes_bool_from_int_arguments(
    tmp_path: Path, record_property,
) -> None:
    stored_args = {**ARGS, "mode": True}
    case = make_case(tmp_path, [proposal(args=stored_args)])
    seed = await seed_terminal(case, success=True)
    await write_operation(case, mutate_record(seed.operation, "args_bool_int"))

    result, before_state, after_state, before_files, after_files = await before_after(
        case, lambda: _reenter(case)
    )
    _record(record_property, stored_args=stored_args, changed_args={**ARGS, "mode": 1},
        result_success=result.success, result_error=result.error,
        before_state=before_state, after_state=after_state,
        before_files=before_files, after_files=after_files)

    assert result.success is False
    assert result.error is not None and "E_OPERATION_ARTIFACT_INVALID:args_mismatch" in result.error
    assert case.model.calls == 1 and case.toolbox.calls == 1 and len(case.probe.calls) == 1
    assert after_state == before_state and after_files == before_files


async def _checkpoint_snapshot_path(case) -> Path:  # type: ignore[no-untyped-def]
    output = (await captured_destination(case)).output_dir

    def discover() -> Path:
        paths = sorted(output.glob("control_plane_checkpoint_snapshot_*.json"))
        assert len(paths) == 1
        return paths[0]

    return await asyncio.to_thread(discover)


# Layer: integration
async def test_completed_replay_refuses_coordinated_snapshot_and_operation_rewrite(
    tmp_path: Path, record_property,
) -> None:
    case = make_case(tmp_path, [proposal()])
    seed = await seed_terminal(case, success=True)
    snapshot_path = await _checkpoint_snapshot_path(case)
    files = AsyncFileTools(case.workspace)
    snapshot_rel = snapshot_path.relative_to(case.workspace).as_posix()
    snapshot = json.loads(await files.read_file(snapshot_rel))
    changed_args = {**ARGS, "content": "coordinated-rewrite"}
    snapshot["tool_calls"][0]["args"] = changed_args
    changed_operation = {**seed.operation, "args": changed_args}
    changed_operation["result_digest"] = case.executor.artifact_writer.hash_payload(changed_operation["result"])
    await files.write_file(snapshot_rel, json.dumps(snapshot, indent=2, ensure_ascii=False))
    await write_operation(case, changed_operation)
    snapshot_before = await files.read_file(snapshot_rel)

    result, before_state, after_state, before_files, after_files = await before_after(
        case, lambda: _reenter(case)
    )
    snapshot_after = await files.read_file(snapshot_rel)
    _record(record_property, persisted_checkpoint_integrity=before_state["checkpoint"]["integrity_verification_ref"],
        changed_args=changed_args, result_success=result.success, result_error=result.error,
        snapshot_before_sha256=hashlib.sha256(snapshot_before.encode("utf-8")).hexdigest(),
        snapshot_after_sha256=hashlib.sha256(snapshot_after.encode("utf-8")).hexdigest(),
        before_state=before_state, after_state=after_state,
        before_files=before_files, after_files=after_files)

    assert result.success is False
    assert result.error is not None and "E_CHECKPOINT_SNAPSHOT_INTEGRITY_MISMATCH" in result.error
    assert case.model.calls == 1 and case.toolbox.calls == 1 and len(case.probe.calls) == 1
    assert after_state == before_state and after_files == before_files
    assert snapshot_after == snapshot_before
