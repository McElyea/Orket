"""Integration: public preview fallback observations retain required native publication."""
import asyncio
import json
import threading

import pytest

from orket.application.services import preview_service as previews
from orket.core.contracts.logging_inputs import LoggingInputs
from orket.logging import bind_logging, prepare_logging
from tests.helpers.runtime_verification_hold import sqlite_response
from tests.integration.test_bug_fix_event_inputs import records

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
EVENTS = {"organization": "preview_org_config_missing", "role": "preview_role_asset_missing"}


def seed(root):
    assets = {"epics/preview": {"id": "preview", "name": "Preview fixture", "team": "preview",
        "environment": "standard", "issues": [{"id": "fixture", "summary": "Preview issue", "seat": "coder"}]},
        "teams/preview": {"name": "Preview fixture", "seats": {"coder": {"name": "Coder", "roles": ["atg_missing_role"]}}}}
    for name, value in assets.items():
        path = root / "model/core" / (name + ".json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")


async def execute(owner):
    return await owner.build_issue_preview("fixture", "preview")


def hold_before_observation(monkeypatch, site):
    entered, release = asyncio.Event(), asyncio.Event()
    actual_loader, actual_thread = previews.run_owned_io, previews.run_owned_thread

    async def loader(operation, *, label, **options):
        async def held():
            entered.set()
            await release.wait()
            return await operation()
        if site == "role" and label == "preview-asset" and operation.args[0] == "roles":
            return await actual_loader(held, label=label, **options)
        return await actual_loader(operation, label=label, **options)

    async def thread(operation, *, label):
        if site == "organization" and label == "preview-organization":
            entered.set()
            await release.wait()
        return await actual_thread(operation, label=label)

    monkeypatch.setattr(previews, "run_owned_io", loader)
    monkeypatch.setattr(previews, "run_owned_thread", thread)
    return entered, release


@pytest.mark.parametrize("site", list(EVENTS))
async def test_public_preview_selects_event_workspace_before_read_wait(tmp_path, monkeypatch, site, record_property):
    await asyncio.to_thread(seed, tmp_path)
    owner = previews.PreviewBuilder(tmp_path / "model", environment={})
    entered, release = hold_before_observation(monkeypatch, site)
    with bind_logging(await prepare_logging(LoggingInputs(tmp_path))):
        task = asyncio.create_task(execute(owner))
        try:
            await asyncio.wait_for(entered.wait(), 3)
            assert await sqlite_response(tmp_path / "observer.sqlite", record_property) < 0.5
            owner.project_root = tmp_path / "late"
            monkeypatch.chdir(tmp_path)
            release.set()
            result = await asyncio.wait_for(task, 5)
            assert result["type"] == "issue" and "Preview issue" in result["compiled_system_prompt"]
            selected = [row for row in await records(tmp_path / "workspace/default/orket.log") if row["event"] == EVENTS[site]]
            assert len(selected) == 1
            assert not [row for row in await records(tmp_path / "late/workspace/default/orket.log") if row["event"] == EVENTS[site]]
        finally:
            release.set()
            await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize("site", list(EVENTS))
@pytest.mark.parametrize("stop", ["none", "cancel", "timeout"])
@pytest.mark.parametrize("failure", ["none", "before", "after"])
async def test_preview_required_observation_settles_before_result(tmp_path, monkeypatch, site, stop, failure, record_property):
    await asyncio.to_thread(seed, tmp_path)
    owner = previews.PreviewBuilder(tmp_path / "model", environment={})
    native = previews.log_event
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    native_failure = OSError("controlled required preview event failure")

    def held(event, payload, **options):
        if event != EVENTS[site]:
            return native(event, payload, **options)
        entered.set()
        try:
            assert release.wait(5)
            if failure == "before":
                raise native_failure
            native(event, payload, **options)
            if failure == "after":
                raise native_failure
        finally:
            finished.set()

    deadline = asyncio.timeout(None)

    async def dispatch():
        async with asyncio.timeout(5), deadline:
            return await execute(owner)

    monkeypatch.setattr(previews, "log_event", held)
    with bind_logging(await prepare_logging(LoggingInputs(tmp_path, timezone_name="MST"))):
        task = asyncio.create_task(dispatch())
        try:
            assert await asyncio.to_thread(entered.wait, 3)
            assert await sqlite_response(tmp_path / "observer.sqlite", record_property) < 0.5
            if stop == "timeout":
                deadline.reschedule(asyncio.get_running_loop().time() + 0.1)
            if stop == "cancel":
                task.cancel()
                await asyncio.sleep(0)
                task.cancel()
            await asyncio.sleep(0.15 if stop == "timeout" else 0)
            assert not task.done()
            release.set()
            outcome, = await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
            assert finished.is_set()
            if failure != "none":
                assert outcome is native_failure
            elif stop != "none":
                assert isinstance(outcome, asyncio.CancelledError if stop == "cancel" else TimeoutError)
            else:
                assert outcome["type"] == "issue" and "Preview issue" in outcome["compiled_system_prompt"]
            rows = [row for row in await records(tmp_path / "workspace/default/orket.log") if row["event"] == EVENTS[site]]
            assert len(rows) == int(failure != "before")
            if rows:
                assert rows[0]["timestamp"].endswith("-07:00")
        finally:
            release.set()
            await asyncio.gather(task, return_exceptions=True)
