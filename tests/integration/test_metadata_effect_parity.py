"""Layer: integration. Real publication interruption and read-only attribution classifications."""
import asyncio
import json
import threading
from types import SimpleNamespace

import pytest

from orket.application.terraform_review.artifacts import write_artifact_bundle
from orket.application.terraform_review.models import canonical_digest
from orket.runtime.execution.phase_c_runtime_truth import (
    SOURCE_ATTRIBUTION_RECEIPT_PATH,
    collect_source_attribution_facts,
    resolve_source_attribution_gate_failure_reason,
)
from tests.helpers.kernel_state_probe import responsive_sqlite
from tests.integration.test_async_file_native_lifetime import hold_native_open

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize('stop', ['cancel', 'timeout'])
@pytest.mark.parametrize('held_name', ['alpha', 'manifest'])
async def test_bundle_interruption_owns_write_and_stops_later_admission(tmp_path, monkeypatch, record_property, stop, held_name):
    root = tmp_path / 'terraform_plan_reviews/fixture'
    target = root / (held_name + '.json')
    state = SimpleNamespace(entered=threading.Event(), release=threading.Event(), finished=threading.Event(), streams=[])
    hold_native_open(monkeypatch, target, state, failure=False)
    deadline = asyncio.timeout(None)
    payloads = {'alpha': {'values': ['first']}, 'beta': {'values': ['second']}}

    async def operation():
        async with deadline:
            return await write_artifact_bundle(workspace=tmp_path, execution_trace_ref='fixture', payloads=payloads)

    timer = threading.Timer(.8, state.release.set)
    timer.start()
    task = asyncio.create_task(operation())
    try:
        assert await asyncio.to_thread(state.entered.wait, 5)
        await responsive_sqlite(tmp_path / 'response.sqlite3', record_property)
        if stop == 'timeout':
            deadline.reschedule(asyncio.get_running_loop().time() + .01)
        else:
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
        await asyncio.sleep(.03)
        assert not task.done() and not state.finished.is_set()
        state.release.set()
        with pytest.raises(TimeoutError if stop == 'timeout' else asyncio.CancelledError):
            await asyncio.wait_for(asyncio.shield(task), 5)
        assert state.streams and all(stream.closed for stream in state.streams)
        assert json.loads(await asyncio.to_thread((root / 'alpha.json').read_text, encoding='utf-8')) == payloads['alpha']
        if held_name == 'alpha':
            assert not await asyncio.to_thread((root / 'beta.json').exists)
            assert not await asyncio.to_thread((root / 'manifest.json').exists)
        else:
            manifest = json.loads(await asyncio.to_thread(target.read_text, encoding='utf-8'))
            for name, payload in payloads.items():
                assert json.loads(await asyncio.to_thread((root / (name + '.json')).read_text, encoding='utf-8')) == payload
                assert manifest['artifact_hashes'][name] == canonical_digest(payload)
    finally:
        state.release.set()
        timer.cancel()
        await asyncio.to_thread(timer.join, 5)
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
        assert await asyncio.to_thread(state.finished.wait, 5)
        for stream in state.streams:
            await asyncio.to_thread(stream.close)
        assert not timer.is_alive()


@pytest.mark.parametrize('mode', ['optional', 'required'])
@pytest.mark.parametrize('kind', ['missing', 'malformed', 'directory', 'null', 'unknown-source', 'valid'])
async def test_attribution_preserves_receipt_classification_without_rewriting(tmp_path, mode, kind):
    target = tmp_path / SOURCE_ATTRIBUTION_RECEIPT_PATH
    await asyncio.to_thread(target.parent.mkdir, parents=True)
    valid = {'claims': [{'claim_id': 'c1', 'claim': 'supported', 'source_ids': ['s1']}],
             'sources': [{'source_id': 's1', 'title': 'source', 'uri': 'fixture:source', 'kind': 'fixture'}]}
    if kind == 'unknown-source':
        valid['claims'][0]['source_ids'] = ['absent']
    before = None
    if kind == 'directory':
        await asyncio.to_thread(target.mkdir)
    elif kind != 'missing':
        before = '{' if kind == 'malformed' else 'null' if kind == 'null' else json.dumps(valid)
        await asyncio.to_thread(target.write_text, before, encoding='utf-8')
    result = await collect_source_attribution_facts(workspace=tmp_path, policy={'source_attribution_mode': mode})
    expected = {'missing': ['source_attribution_receipt_missing'],
                'malformed': ['source_attribution_receipt_invalid_json'],
                'directory': ['source_attribution_receipt_invalid_json'],
                'null': ['source_attribution_claims_missing', 'source_attribution_sources_missing'],
                'unknown-source': ['source_attribution_claim_source_missing'], 'valid': []}[kind]
    assert result['missing_requirements'] == expected
    assert result['synthesis_status'] == ('verified' if not expected else 'blocked' if mode == 'required' else 'optional_unverified')
    assert resolve_source_attribution_gate_failure_reason(result) == (expected[0] if expected and mode == 'required' else None)
    if before is not None:
        assert await asyncio.to_thread(target.read_text, encoding='utf-8') == before
    else:
        assert await asyncio.to_thread(target.exists) is (kind == 'directory')


async def test_missing_unconfigured_receipt_retains_captured_provenance(tmp_path, monkeypatch, record_property):
    from tests.integration.test_async_file_invocation_inputs import hold_path_method

    state = hold_path_method(monkeypatch, 'exists', tmp_path / SOURCE_ATTRIBUTION_RECEIPT_PATH)
    entry = {'artifact_path': SOURCE_ATTRIBUTION_RECEIPT_PATH, 'artifact_type': 'json', 'generator': 'fixture',
             'generator_version': '1', 'source_hash': 'sha256:fixture', 'produced_at': '2036-03-05T12:00:00Z',
             'truth_classification': 'direct', 'operation_id': 'original', 'control_plane_run_id': 'run-original'}
    facts = {'artifacts': [entry]}
    task = asyncio.create_task(collect_source_attribution_facts(workspace=tmp_path, artifact_provenance_facts=facts))
    try:
        assert await asyncio.to_thread(state.entered.wait, 5)
        await responsive_sqlite(tmp_path / 'response.sqlite3', record_property)
        entry.update(operation_id='changed', control_plane_run_id='run-changed')
        facts['artifacts'].clear()
        state.release.set()
        result = await asyncio.wait_for(task, 5)
        assert result['receipt_operation_id'] == 'original' and result['control_plane_run_id'] == 'run-original'
        assert result['artifact_provenance_verified'] and result['synthesis_status'] == 'optional_unverified'
        assert result['missing_requirements'] == ['source_attribution_receipt_missing']
    finally:
        state.release.set()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
        assert state.finished.is_set()
