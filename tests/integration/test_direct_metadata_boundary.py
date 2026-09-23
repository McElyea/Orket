"""Layer: integration. Actual artifact publication and source-attribution reads."""
import asyncio
import json
import threading
import time
from pathlib import Path

import pytest

from orket.adapters.storage.async_card_repository import AsyncCardRepository
from orket.application.terraform_review.artifacts import write_artifact_bundle
from orket.core.domain.records import IssueRecord
from orket.runtime.execution.phase_c_runtime_truth import (
    SOURCE_ATTRIBUTION_RECEIPT_PATH,
    collect_source_attribution_facts,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def hold_metadata(monkeypatch, target, method, enabled):
    original = getattr(Path, method)
    entered, release = threading.Event(), threading.Event()
    threads, timers = [], []

    def observed(path, *args, **options):
        if enabled and path == target and not entered.is_set():
            threads.append(threading.get_ident())
            entered.set()
            timer = threading.Timer(.75, release.set)
            timers.append(timer)
            timer.start()
            assert release.wait(5), 'Metadata fixture release missed'
        return original(path, *args, **options)

    monkeypatch.setattr(Path, method, observed)
    return entered, release, threads, timers


@pytest.mark.parametrize('kind', ['artifact', 'attribution'])
@pytest.mark.parametrize('held', [False, True], ids=['healthy', 'native-hold'])
async def test_application_metadata_preserves_sqlite_response(tmp_path, monkeypatch, record_property, kind, held):
    workspace = tmp_path / kind
    target = (workspace / 'terraform_plan_reviews/fixture/alpha.json' if kind == 'artifact' else
              workspace / SOURCE_ATTRIBUTION_RECEIPT_PATH)
    entered, release, threads, timers = hold_metadata(
        monkeypatch, target, 'resolve' if kind == 'artifact' else 'exists', held)
    started = time.perf_counter()

    async def sqlite():
        cards = AsyncCardRepository(tmp_path / 'response.sqlite3')
        await cards.save(IssueRecord(id='metadata', seat='fixture', summary='Concurrent metadata observation'))
        assert (await cards.get_by_id('metadata')).id == 'metadata'
        return time.perf_counter() - started

    operation = (write_artifact_bundle(workspace=workspace, execution_trace_ref='fixture', payloads={'alpha': {'value': 42}})
                 if kind == 'artifact' else collect_source_attribution_facts(workspace=workspace))
    task, probe = asyncio.create_task(operation), asyncio.create_task(sqlite())
    try:
        result, elapsed = await asyncio.wait_for(asyncio.gather(task, probe), 5)
        record_property('responsive_sqlite_seconds', elapsed)
        if held:
            assert entered.is_set() and threads == [threads[0]] and threads[0] != threading.get_ident()
        assert elapsed < .5
        if kind == 'artifact':
            assert result.artifact_paths['alpha'] == str(target)
            assert json.loads(await asyncio.to_thread(target.read_text, encoding='utf-8')) == {'value': 42}
        else:
            assert result == {}
    finally:
        release.set()
        await asyncio.wait_for(asyncio.gather(task, probe, return_exceptions=True), 5)
        for timer in timers:
            await asyncio.to_thread(timer.join, 5)
