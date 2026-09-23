"""Layer: integration. Real response-artifact lifetime and captured-input controls.

This direct production publication probe uses real files and SQLite. It does not
establish whole-turn/model acceptance or any other artifact writer's ownership.
"""
from __future__ import annotations

import asyncio
import json
import os
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.application.workflows.turn_artifact_destination import TurnArtifactDestination
from orket.application.workflows.turn_artifact_writer import TurnArtifactWriter
from orket.application.workflows.turn_executor_model_artifacts import write_response_artifacts
from orket.application.workflows.turn_response_capture import capture_turn_response
from tests.helpers.kernel_state_probe import responsive_sqlite

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
_NATIVE_RESPONSE_BYTES = ('original response' + os.linesep).encode('utf-8')


def _paths(workspace: Path) -> tuple[Path, Path]:
    directory = workspace / 'observability' / 'artifact-session' / 'artifact-issue' / '001_reviewer'
    return directory / 'model_response.txt', directory / 'model_response_raw.json'


def _hold_write(monkeypatch, target: Path, fault: bool):
    state = SimpleNamespace(entered=threading.Event(), release=threading.Event(),
                            finished=threading.Event(), threads=[], fault='', calls=[])
    original = Path.write_text

    def held(path, *args, **kwargs):
        if path != target:
            return original(path, *args, **kwargs)
        state.calls.append(str(path))
        state.threads.append(threading.get_ident())
        state.entered.set()
        try:
            assert state.release.wait(5), 'Native artifact write was not released'
            if fault:
                path.mkdir()
            try:
                return original(path, *args, **kwargs)
            except (PermissionError, IsADirectoryError) as error:
                state.fault = type(error).__name__
                raise
        finally:
            state.finished.set()

    monkeypatch.setattr(Path, 'write_text', held)
    return state


async def _publish(writer, response):
    destination = TurnArtifactDestination(
        writer=writer, workspace=writer.workspace, session_id='artifact-session',
        issue_id='artifact-issue', role_name='reviewer', role_id='REVIEWER', turn_index=1,
    )
    await write_response_artifacts(
        destination=destination, response=capture_turn_response(response),
    )


async def _settle(task, state, target, raw, record_property, before_release):
    state.release.set()
    await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
    if state.entered.is_set():
        assert await asyncio.to_thread(state.finished.wait, 5)
    is_file, is_directory, raw_exists = await asyncio.gather(
        asyncio.to_thread(target.is_file), asyncio.to_thread(target.is_dir),
        asyncio.to_thread(raw.exists))
    content = await asyncio.to_thread(target.read_bytes) if is_file else None
    record_property('artifact_lifetime_observation', json.dumps(dict(
        before_release=before_release, native_finished=state.finished.is_set(),
        native_error=state.fault, first_is_file=is_file, first_is_directory=is_directory,
        first_bytes=None if content is None else content.decode('utf-8'),
        raw_exists=raw_exists, write_calls=state.calls), sort_keys=True))


@pytest.mark.parametrize('fault', [False, True], ids=['write', 'late-directory-fault'])
@pytest.mark.parametrize('stop', ['none', 'cancel', 'timeout'])
async def test_response_publication_retains_admitted_write(
    tmp_path, monkeypatch, record_property, fault, stop,
):
    """Layer: integration. The first real write drains before return."""
    target, raw = _paths(tmp_path)
    state = _hold_write(monkeypatch, target, fault)
    response = dict(content='original response\n', model='controlled-model')
    deadline = asyncio.timeout(None)

    async def operation():
        async with asyncio.timeout(5), deadline:
            await _publish(TurnArtifactWriter(tmp_path), response)

    task = asyncio.create_task(operation())
    before_release = {}
    primary_error = None
    try:
        assert await asyncio.to_thread(state.entered.wait, 5)
        await responsive_sqlite(tmp_path / 'independent.sqlite3', record_property)
        assert state.threads == [state.threads[0]] and state.threads[0] != threading.get_ident()
        if stop == 'cancel':
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
        elif stop == 'timeout':
            deadline.reschedule(asyncio.get_running_loop().time() + .01)
        if stop != 'none':
            await asyncio.sleep(.03)
        before_release.update(task_done=task.done(), native_finished=state.finished.is_set())
        assert not task.done() and not state.finished.is_set()
        state.release.set()
        if fault:
            with pytest.raises((PermissionError, IsADirectoryError)):
                await asyncio.wait_for(asyncio.shield(task), 5)
        elif stop == 'none':
            await asyncio.wait_for(asyncio.shield(task), 5)
            assert json.loads(await asyncio.to_thread(raw.read_bytes)) == response
        else:
            with pytest.raises(asyncio.CancelledError if stop == 'cancel' else TimeoutError):
                await asyncio.wait_for(asyncio.shield(task), 5)
        assert state.finished.is_set()
        if not fault:
            assert await asyncio.to_thread(target.read_bytes) == _NATIVE_RESPONSE_BYTES
        if fault or stop != 'none':
            assert not await asyncio.to_thread(raw.exists)
    except BaseException as error:
        primary_error = error
        raise
    finally:
        try:
            await _settle(task, state, target, raw, record_property, before_release)
        except BaseException as error:
            if primary_error is None:
                raise
            primary_error.add_note(f'Artifact cleanup also failed: {error!r}')


async def test_response_publication_captures_raw_payload_before_first_write(
    tmp_path, monkeypatch, record_property,
):
    """Layer: integration. Entry response bytes survive later mutation."""
    target, raw = _paths(tmp_path)
    state = _hold_write(monkeypatch, target, False)
    response = dict(content='original response\n', metadata={'profile': 'original-profile'})
    expected = json.loads(json.dumps(response))
    task = asyncio.create_task(_publish(TurnArtifactWriter(tmp_path), response))
    primary_error = None
    try:
        assert await asyncio.to_thread(state.entered.wait, 5)
        await responsive_sqlite(tmp_path / 'independent.sqlite3', record_property)
        response['content'] = 'changed after native admission'
        response['metadata']['profile'] = 'changed-profile'
        state.release.set()
        await asyncio.wait_for(asyncio.shield(task), 5)
        physical = json.loads(await asyncio.to_thread(raw.read_bytes))
        record_property('artifact_payload_observation', json.dumps(physical, sort_keys=True))
        assert await asyncio.to_thread(target.read_bytes) == _NATIVE_RESPONSE_BYTES
        assert physical == expected
    except BaseException as error:
        primary_error = error
        raise
    finally:
        try:
            await _settle(task, state, target, raw, record_property, {})
        except BaseException as error:
            if primary_error is None:
                raise
            primary_error.add_note(f'Artifact cleanup also failed: {error!r}')


@pytest.mark.parametrize('fault', [False, True], ids=['write', 'late-directory-fault'])
@pytest.mark.parametrize('stop', ['none', 'cancel', 'timeout'])
async def test_response_raw_publication_retains_admitted_second_write(
    tmp_path, monkeypatch, record_property, fault, stop,
):
    """Layer: integration. The second real write drains before return."""
    text_path, raw_path = _paths(tmp_path)
    state = _hold_write(monkeypatch, raw_path, fault)
    response = dict(content='original response\n', metadata={'profile': 'original-profile'})
    deadline = asyncio.timeout(None)

    async def operation():
        async with asyncio.timeout(5), deadline:
            await _publish(TurnArtifactWriter(tmp_path), response)

    task = asyncio.create_task(operation())
    primary_error = None
    try:
        assert await asyncio.to_thread(state.entered.wait, 5)
        await responsive_sqlite(tmp_path / 'independent.sqlite3', record_property)
        assert await asyncio.to_thread(text_path.read_bytes) == _NATIVE_RESPONSE_BYTES
        if stop == 'cancel':
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
        elif stop == 'timeout':
            deadline.reschedule(asyncio.get_running_loop().time() + .01)
        if stop != 'none':
            await asyncio.sleep(.03)
        assert not task.done() and not state.finished.is_set()
        state.release.set()
        if fault:
            with pytest.raises((PermissionError, IsADirectoryError)):
                await asyncio.wait_for(asyncio.shield(task), 5)
            assert await asyncio.to_thread(raw_path.is_dir)
        elif stop == 'none':
            await asyncio.wait_for(asyncio.shield(task), 5)
            assert json.loads(await asyncio.to_thread(raw_path.read_bytes)) == response
        else:
            with pytest.raises(asyncio.CancelledError if stop == 'cancel' else TimeoutError):
                await asyncio.wait_for(asyncio.shield(task), 5)
            assert json.loads(await asyncio.to_thread(raw_path.read_bytes)) == response
        assert state.finished.is_set()
    except BaseException as error:
        primary_error = error
        raise
    finally:
        try:
            await _settle(task, state, raw_path, raw_path, record_property, {})
        except BaseException as error:
            if primary_error is None:
                raise
            primary_error.add_note(f'Artifact cleanup also failed: {error!r}')


async def test_response_raw_render_failure_precedes_first_artifact(tmp_path):
    """Layer: integration. Rendering failure precedes physical publication."""
    response = {'content': 'must not publish'}
    response['cycle'] = response
    text_path, raw_path = _paths(tmp_path)

    with pytest.raises(ValueError, match='Circular reference'):
        await _publish(TurnArtifactWriter(tmp_path), response)

    assert not await asyncio.to_thread(text_path.exists)
    assert not await asyncio.to_thread(raw_path.exists)
