"""Layer: integration. Validation path-metadata ownership controls.

This module exercises ContractValidator through the async production observation
entrypoint. It is not whole-executor proof.
"""

from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import aiosqlite
import pytest

from orket.application.workflows.turn_contract_validator import ContractValidator
from orket.application.workflows.turn_read_context import observe_legacy_required_read_paths
from orket.application.workflows.turn_response_parser import ResponseParser
from orket.core.domain.execution import ExecutionTurn, ToolCall
from orket.schema import RoleConfig
from tests.helpers.turn_artifacts import artifact_test_utc_now

pytestmark = pytest.mark.integration
_ORDINARY_TOKEN = "agent_output/review.txt"
_MISSING_TOKEN = "agent_output/missing.txt"
_DIRECTORY_TOKEN = "agent_output/review-directory"
_OUTSIDE_TOKEN = "../outside.txt"


def _create_fixture(root: Path) -> tuple[Path, Path, Path, Path]:
    workspace = root / "workspace"
    ordinary = workspace / _ORDINARY_TOKEN
    directory = workspace / _DIRECTORY_TOKEN
    outside = root / "outside.txt"
    ordinary.parent.mkdir(parents=True)
    directory.mkdir()
    ordinary.write_bytes(b"ordinary validation input\n")
    outside.write_bytes(b"legacy outside classification\n")
    return workspace, ordinary, directory, outside


def _validator(workspace: Path) -> ContractValidator:
    return ContractValidator(ResponseParser(utc_now=artifact_test_utc_now))


def _role() -> RoleConfig:
    return RoleConfig(
        id="reviewer",
        summary="reviewer",
        description="Review declared files",
        tools=["read_file"],
    )


def _context() -> dict[str, object]:
    return {
        "required_action_tools": ["read_file"],
        "required_read_paths": [
            _ORDINARY_TOKEN,
            _MISSING_TOKEN,
            _DIRECTORY_TOKEN,
            _OUTSIDE_TOKEN,
        ],
    }


def _turn() -> ExecutionTurn:
    return ExecutionTurn(
        timestamp=None,
        role="reviewer",
        issue_id="ISSUE-VALIDATION-PATH",
        content="",
        tool_calls=[ToolCall(tool="read_file", args={"path": _ORDINARY_TOKEN})],
    )


def _assert_violation_classification(violations: list[dict[str, object]]) -> None:
    expected = [_ORDINARY_TOKEN, _OUTSIDE_TOKEN]
    read_violation = next(
        item for item in violations if item.get("reason") == "read_path_contract_not_met"
    )
    assert read_violation["required_read_paths"] == expected
    assert _MISSING_TOKEN not in read_violation["required_read_paths"]
    assert _DIRECTORY_TOKEN not in read_violation["required_read_paths"]


def _hold_target_resolve(monkeypatch, target: Path, *, enabled: bool):
    state = SimpleNamespace(
        entered=threading.Event(),
        release=threading.Event(),
        finished=threading.Event(),
        threads=[],
        timers=[],
    )
    original = Path.resolve

    def observed(path, *args, **kwargs):
        if enabled and path == target and not state.entered.is_set():
            state.threads.append(threading.get_ident())
            state.entered.set()
            timer = threading.Timer(0.8, state.release.set)
            timer.daemon = True
            state.timers.append(timer)
            timer.start()
            try:
                assert state.release.wait(5), "Native validation metadata was not released"
            finally:
                state.finished.set()
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", observed)
    return state


async def _collect_current_route(
    validator: ContractValidator,
    turn: ExecutionTurn,
    role: RoleConfig,
    context: dict[str, object],
    *, workspace: Path,
) -> list[dict[str, object]]:
    observation = await observe_legacy_required_read_paths(
        context=context, workspace=workspace,
    )
    return validator.collect_contract_violations(turn, role, context, observation)


async def _sqlite_elapsed(database: Path, admitted_at: float) -> float:
    async with aiosqlite.connect(database) as connection:
        assert await (await connection.execute("SELECT 42")).fetchone() == (42,)
    return time.perf_counter() - admitted_at


async def _assert_fixture_unchanged(
    workspace: Path,
    ordinary: Path,
    outside: Path,
    before: tuple[bytes, bytes],
) -> None:
    ordinary_after, outside_after, directory_ok, missing_absent = await asyncio.gather(
        asyncio.to_thread(ordinary.read_bytes),
        asyncio.to_thread(outside.read_bytes),
        asyncio.to_thread((workspace / _DIRECTORY_TOKEN).is_dir),
        asyncio.to_thread(lambda: not (workspace / _MISSING_TOKEN).exists()),
    )
    assert (ordinary_after, outside_after) == before
    assert directory_ok
    assert missing_absent


def _raise_cleanup_errors(errors: list[BaseException]) -> None:
    if not errors:
        return
    first, *rest = errors
    for error in rest:
        first.add_note(f"Additional cleanup failure: {error!r}")
    raise first


async def _settle_probe(
    task: asyncio.Task,
    probe: asyncio.Task,
    state,
    workspace: Path,
    ordinary: Path,
    outside: Path,
    before: tuple[bytes, bytes],
) -> None:
    errors: list[BaseException] = []
    state.release.set()
    try:
        await asyncio.wait_for(asyncio.gather(task, probe, return_exceptions=True), 5)
    except BaseException as error:
        errors.append(error)
    for timer in state.timers:
        timer.cancel()
        try:
            await asyncio.to_thread(timer.join, 5)
        except BaseException as error:
            errors.append(error)
    if state.entered.is_set():
        try:
            assert await asyncio.to_thread(state.finished.wait, 5)
        except BaseException as error:
            errors.append(error)
    try:
        assert all(not timer.is_alive() for timer in state.timers)
        await _assert_fixture_unchanged(workspace, ordinary, outside, before)
    except BaseException as error:
        errors.append(error)
    _raise_cleanup_errors(errors)


@pytest.mark.asyncio
async def test_contract_validator_preserves_legacy_path_classification(tmp_path: Path) -> None:
    workspace, ordinary, directory, outside = await asyncio.to_thread(_create_fixture, tmp_path)
    before = await asyncio.gather(
        asyncio.to_thread(ordinary.read_bytes), asyncio.to_thread(outside.read_bytes)
    )
    validator = _validator(workspace)
    context = _context()

    try:
        observation = await observe_legacy_required_read_paths(context=context, workspace=workspace)
        violations = validator.collect_contract_violations(_turn(), _role(), context, observation)
        assert observation.existing == (_ORDINARY_TOKEN, _OUTSIDE_TOKEN)
        _assert_violation_classification(violations)
        assert await asyncio.to_thread(directory.is_dir)
        assert await asyncio.to_thread(lambda: not (workspace / _MISSING_TOKEN).exists())
    finally:
        assert await asyncio.gather(
            asyncio.to_thread(ordinary.read_bytes), asyncio.to_thread(outside.read_bytes)
        ) == list(before)


@pytest.mark.asyncio
@pytest.mark.parametrize("held", [False, True], ids=["healthy", "native-hold"])
async def test_validation_path_metadata_preserves_sqlite_response(
    tmp_path: Path,
    monkeypatch,
    record_property,
    held: bool,
) -> None:
    workspace, ordinary, _directory, outside = await asyncio.to_thread(
        _create_fixture, tmp_path
    )
    before = await asyncio.gather(
        asyncio.to_thread(ordinary.read_bytes),
        asyncio.to_thread(outside.read_bytes),
    )
    state = _hold_target_resolve(monkeypatch, ordinary, enabled=held)
    admitted_at = time.perf_counter()
    task = asyncio.create_task(
        _collect_current_route(_validator(workspace), _turn(), _role(), _context(), workspace=workspace)
    )
    probe = asyncio.create_task(
        _sqlite_elapsed(tmp_path / "validation-responsive.sqlite3", admitted_at)
    )
    primary_error: BaseException | None = None

    try:
        violations, elapsed = await asyncio.wait_for(asyncio.gather(task, probe), 5)
        record_property("responsive_sqlite_seconds", elapsed)
        assert elapsed < 0.5
        _assert_violation_classification(violations)
        if held:
            assert state.entered.is_set() and state.finished.is_set()
            assert state.threads and state.threads[0] != threading.get_ident()
    except BaseException as error:
        primary_error = error
        raise
    finally:
        try:
            await _settle_probe(
                task, probe, state, workspace, ordinary, outside, tuple(before)
            )
        except BaseException as cleanup_error:
            if primary_error is None:
                raise
            primary_error.add_note(f"Validation metadata cleanup failed: {cleanup_error!r}")
