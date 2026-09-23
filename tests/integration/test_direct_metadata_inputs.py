"""Layer: integration. Actual artifact/read inputs survive later caller mutation."""
import asyncio
import io
import json
import threading
from pathlib import Path

import aiofiles.threadpool
import pytest

from orket.application.terraform_review.artifacts import write_artifact_bundle
from orket.application.terraform_review.models import canonical_digest
from orket.runtime.execution.phase_c_runtime_truth import (
    SOURCE_ATTRIBUTION_RECEIPT_PATH,
    collect_source_attribution_facts,
)
from tests.helpers.kernel_state_probe import responsive_sqlite
from tests.integration.test_async_file_invocation_inputs import hold_path_method

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_artifact_manifest_retains_nested_payloads_and_invocation_root(tmp_path, monkeypatch, record_property):
    original, changed = tmp_path / 'original', tmp_path / 'changed'
    await asyncio.to_thread(original.mkdir)
    await asyncio.to_thread(changed.mkdir)
    monkeypatch.chdir(original)
    root = original / 'workspace/terraform_plan_reviews/fixture'
    state = hold_path_method(monkeypatch, 'mkdir', root)
    payloads = {'alpha': {'values': ['first']}, 'beta': {'values': ['second']}}
    expected = json.loads(json.dumps(payloads))
    task = asyncio.create_task(write_artifact_bundle(workspace=Path('workspace'), execution_trace_ref='fixture', payloads=payloads))
    try:
        assert await asyncio.to_thread(state.entered.wait, 5)
        await responsive_sqlite(tmp_path / 'response.sqlite3', record_property)
        payloads['beta']['values'].append('later mutation')
        monkeypatch.chdir(changed)
        state.release.set()
        result = await asyncio.wait_for(task, 5)
        assert result.artifact_dir == str(root)
        manifest = json.loads(await asyncio.to_thread((root / 'manifest.json').read_text, encoding='utf-8'))
        for name, payload in expected.items():
            path = root / (name + '.json')
            actual = json.loads(await asyncio.to_thread(path.read_text, encoding='utf-8'))
            assert actual == payload
            assert result.artifact_paths[name] == manifest['artifact_paths'][name] == str(path)
            assert result.artifact_hashes[name] == manifest['artifact_hashes'][name] == canonical_digest(actual)
        assert not await asyncio.to_thread((changed / 'workspace').exists)
    finally:
        state.release.set()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
        assert state.finished.is_set()


def hold_receipt_open(monkeypatch, original_root, target):
    original = io.open
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()

    def observed(file, *args, **options):
        if isinstance(file, int):
            return original(file, *args, **options)
        path = Path(file)
        absolute = path if path.is_absolute() else original_root / path
        if absolute == target and not entered.is_set():
            entered.set()
            try:
                assert release.wait(5), 'Receipt observation fixture was not released'
                return original(file, *args, **options)
            finally:
                finished.set()
        return original(file, *args, **options)

    monkeypatch.setattr(io, 'open', observed)
    monkeypatch.setattr(aiofiles.threadpool, 'sync_open', observed)
    return entered, release, finished


async def test_attribution_retains_receipt_root_across_native_admission(tmp_path, monkeypatch, record_property):
    original, changed = tmp_path / 'original', tmp_path / 'changed'
    receipt = {'claims': [{'claim_id': 'c1', 'claim': 'original', 'source_ids': ['s1']}],
               'sources': [{'source_id': 's1', 'title': 'source', 'uri': 'fixture:original', 'kind': 'fixture'}]}
    for root in (original, changed):
        target = root / 'workspace' / SOURCE_ATTRIBUTION_RECEIPT_PATH
        await asyncio.to_thread(target.parent.mkdir, parents=True)
        await asyncio.to_thread(target.write_text, json.dumps(receipt if root == original else {}), encoding='utf-8')
    monkeypatch.chdir(original)
    entered, release, finished = hold_receipt_open(monkeypatch, original, original / 'workspace' / SOURCE_ATTRIBUTION_RECEIPT_PATH)
    policy = {'source_attribution_mode': 'required'}
    task = asyncio.create_task(collect_source_attribution_facts(workspace=Path('workspace'), policy=policy))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        await responsive_sqlite(tmp_path / 'response.sqlite3', record_property)
        policy['source_attribution_mode'] = 'optional'
        monkeypatch.chdir(changed)
        release.set()
        result = await asyncio.wait_for(task, 5)
        assert result['mode'] == 'required' and result['synthesis_status'] == 'verified'
        assert result['claims'] == receipt['claims'] and result['sources'] == receipt['sources']
    finally:
        release.set()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
        assert finished.is_set()
