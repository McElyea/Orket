"""Captured observations for the orphaned step/journal terminal opening."""
from __future__ import annotations

import hashlib
import json
from functools import partial
from pathlib import Path
from typing import Any

import aiosqlite

from orket.adapters.execution.owned_io import run_owned_thread
from orket.application.services.turn_tool_control_plane_closeout import finalize_turn_execution_atomic
from orket.application.services.turn_tool_control_plane_resource_lifecycle import namespace_resource_id_for_run
from orket.application.services.turn_tool_control_plane_service import TurnToolControlPlaneError
from orket.core.contracts.turn_tool_dispatch import is_unresolved_tool_dispatch
from orket.logging import settle_log_write_frontier
from tests.helpers.operation_binding import (
    ATTEMPT_ID,
    RUN_ID,
    _dump,
    _paths_sync,
    control_plane_state,
    operation_id,
)

__test__ = False
PRIOR_READ_PATH = "fixture/approval-input.txt"
PRIOR_READ_TEXT = "controlled approval input"


def prepare_approval_prior_read_assets(root: Path, workspace: Path) -> None:
    """Add one declared read-only tool and its physical input before engine construction."""
    role_path = root / "model/core/roles/lead_architect.json"
    role = json.loads(role_path.read_text(encoding="utf-8"))
    assert role["tools"] == ["write_file", "update_issue_status"]
    role["tools"] = ["read_file", *role["tools"]]
    role_path.write_text(json.dumps(role, sort_keys=True), encoding="utf-8")
    epic_path = root / "model/core/epics/approval_required.json"
    epic = json.loads(epic_path.read_text(encoding="utf-8"))
    params = epic["issues"][0]["params"]
    assert "artifact_contract" not in params
    params["artifact_contract"] = {"required_read_paths": [PRIOR_READ_PATH]}
    epic_path.write_text(json.dumps(epic, sort_keys=True), encoding="utf-8")
    read_path = workspace / PRIOR_READ_PATH
    read_path.parent.mkdir(parents=True)
    read_path.write_text(PRIOR_READ_TEXT, encoding="utf-8")


async def remove_journal(
    database,
    *,
    journal_id: str,
    run_id: str,
    attempt_id: str,
    step_id: str,
) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Delete one exact journal row after binding its complete execution identity."""
    async with aiosqlite.connect(database) as connection:
        cursor = await connection.execute(
            "SELECT payload_json FROM effect_journal_entries "
            "WHERE journal_entry_id = ? AND run_id = ?",
            (journal_id, run_id),
        )
        rows = await cursor.fetchall()
        assert len(rows) == 1
        payload = json.loads(str(rows[0][0]))
        assert payload["journal_entry_id"] == journal_id
        assert payload["run_id"] == run_id
        assert payload["attempt_id"] == attempt_id
        assert payload["step_id"] == step_id
        deleted = await connection.execute(
            "DELETE FROM effect_journal_entries WHERE journal_entry_id = ? AND run_id = ?",
            (journal_id, run_id),
        )
        assert deleted.rowcount == 1
        await connection.commit()
    return payload


async def remove_current_journal(case) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Delete exactly the coherent current-attempt journal row, retaining its resolved step."""
    payload = await remove_journal(
        case.database,
        journal_id=f"turn-tool-journal:{operation_id()}",
        run_id=RUN_ID,
        attempt_id=ATTEMPT_ID,
        step_id=operation_id(),
    )
    step = await case.service.execution_repository.get_step_record(step_id=operation_id())
    effects = await case.service.publication.repository.list_effect_journal_entries(run_id=RUN_ID)
    assert step is not None and not is_unresolved_tool_dispatch(step)
    assert effects == []
    return payload


async def remove_current_step(case) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Create the journal-only control by deleting the one exact paired step row."""
    async with aiosqlite.connect(case.database) as connection:
        cursor = await connection.execute(
            "SELECT payload_json FROM control_plane_steps WHERE step_id = ? AND attempt_id = ?",
            (operation_id(), ATTEMPT_ID),
        )
        rows = await cursor.fetchall()
        assert len(rows) == 1
        payload = json.loads(str(rows[0][0]))
        assert payload["step_id"] == operation_id()
        assert payload["attempt_id"] == ATTEMPT_ID
        deleted = await connection.execute(
            "DELETE FROM control_plane_steps WHERE step_id = ? AND attempt_id = ?",
            (operation_id(), ATTEMPT_ID),
        )
        assert deleted.rowcount == 1
        await connection.commit()
    assert await case.service.execution_repository.get_step_record(step_id=operation_id()) is None
    return payload


def _physical_sync(case) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    paths = _paths_sync(case)
    observed: dict[str, Any] = {"toolbox_calls": case.toolbox.calls}
    for name in ("operation", "effect"):
        path = paths[name]
        raw = path.read_bytes()
        observed[name] = {
            "path": str(path.resolve()),
            "size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
        if name == "effect":
            observed[name]["utf8"] = raw.decode("utf-8")
    return observed


async def physical_state(case) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    return await run_owned_thread(
        partial(_physical_sync, case),
        label="step-journal-opening-physical-readback",
    )


def _tree_sync(root) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    settle_log_write_frontier()
    resolved = root.resolve()
    files: dict[str, Any] = {}
    for path in sorted(resolved.rglob("*")):
        if path.is_file():
            raw = path.read_bytes()
            files[path.relative_to(resolved).as_posix()] = {
                "size": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
    return {"root": str(resolved), "log_write_frontier": "settled", "files": files}


async def physical_tree_state(root) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    return await run_owned_thread(
        partial(_tree_sync, root),
        label="step-journal-approval-physical-readback",
    )


async def logical_state(case) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    state = await control_plane_state(case)
    run = await case.service.execution_repository.get_run_record(run_id=RUN_ID)
    assert run is not None
    resource = await case.service.publication.repository.get_latest_resource_record(
        resource_id=namespace_resource_id_for_run(run=run)
    )
    state["resource"] = None if resource is None else _dump(resource)
    return state


async def observe_terminal(
    case,
    *,
    executed_step_count: int | None,
    violation_reasons: list[str],
    authoritative_result_ref: str,
) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    before_logical = await logical_state(case)
    before_physical = await physical_state(case)
    try:
        returned = await finalize_turn_execution_atomic(
            transactions=case.service.transactions,
            authority=case.service.publication.authority,
            run_id=RUN_ID,
            attempt_id=ATTEMPT_ID,
            authoritative_result_ref=authoritative_result_ref,
            violation_reasons=list(violation_reasons),
            executed_step_count=executed_step_count,
            error_type=TurnToolControlPlaneError,
        )
    except TurnToolControlPlaneError as exc:
        outcome: dict[str, Any] = {
            "kind": "error",
            "type": type(exc).__name__,
            "message": str(exc),
        }
    else:
        outcome = {"kind": "returned", "records": [_dump(record) for record in returned]}
    after_logical = await logical_state(case)
    after_physical = await physical_state(case)
    return {
        "executed_step_count": executed_step_count,
        "violation_reasons": list(violation_reasons),
        "outcome": outcome,
        "before_logical": before_logical,
        "after_logical": after_logical,
        "before_physical": before_physical,
        "after_physical": after_physical,
    }
