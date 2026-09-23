"""Layer: integration. Packet-2 observes physical receipts without changing their authority."""
import asyncio
import json

import pytest

from orket.adapters.storage.async_card_repository import AsyncCardRepository
from orket.runtime.execution.phase_c_runtime_truth import collect_phase_c_packet2_facts

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding='utf-8')


def write_legacy_turn(workspace, *, issue='ISSUE', turn='001_coder'):
    directory = workspace / 'observability/run' / issue / turn
    write_json(directory / 'parsed_tool_calls.json', [{'tool': 'write_file', 'args': {'path': 'agent_output/result.txt'}}])
    # Independently fixed canonical fixture key, not obtained from the runtime under test.
    result = directory / 'tool_result_write_file_fb495988c6db.json'
    write_json(result, {'ok': True, 'path': 'agent_output/result.txt'})
    target = workspace / 'agent_output/result.txt'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('physical output', encoding='utf-8')
    return directory, result


def receipt_row(operation, *, path='agent_output/result.txt', sequence=1, ok=True):
    return {'tool': 'write_file', 'operation_id': operation, 'receipt_seq': sequence,
            'tool_args': {'path': path}, 'execution_result': {'ok': ok, 'path': path}}


def workspace_bytes(workspace):
    return {path.relative_to(workspace).as_posix(): path.read_bytes() for path in workspace.rglob('*') if path.is_file()}


async def observe(workspace, tmp_path):
    before = await asyncio.to_thread(workspace_bytes, workspace)
    result = await collect_phase_c_packet2_facts(workspace=workspace, run_id='run',
                                                cards_repo=AsyncCardRepository(tmp_path / 'cards.sqlite3'))
    assert await asyncio.to_thread(workspace_bytes, workspace) == before
    return result


@pytest.mark.parametrize('protocol', ['absent', 'empty', 'malformed', 'non-object', 'directory', 'valid'])
async def test_protocol_file_precedence_preserves_legacy_exclusion(tmp_path, protocol):
    workspace = tmp_path / 'workspace'
    directory, _ = await asyncio.to_thread(write_legacy_turn, workspace)
    target = directory / 'protocol_receipts.log'
    if protocol == 'directory':
        await asyncio.to_thread(target.mkdir)
    elif protocol != 'absent':
        text = {'empty': '', 'malformed': '{\n', 'non-object': 'null\n[]\n',
                'valid': json.dumps(receipt_row('protocol-write')) + '\n'}[protocol]
        await asyncio.to_thread(target.write_text, text, encoding='utf-8')
    result = await observe(workspace, tmp_path)
    if protocol in {'absent', 'valid'}:
        entry, = result['narration_to_effect_audit']['entries']
        expected = 'legacy:issue:coder:001:000:write_file:fb495988c6db' if protocol == 'absent' else 'protocol-write'
        assert entry['operation_id'] == expected
        assert entry['audit_status'] == 'verified'
        assert entry['issue_id'] == 'ISSUE' and entry['role_name'] == 'coder' and entry['turn_index'] == 1
    else:
        assert 'narration_to_effect_audit' not in result and 'idempotency' not in result


async def test_protocol_sorting_tolerant_rows_identity_and_manifest_are_preserved(tmp_path):
    workspace = tmp_path / 'workspace'
    directory, _ = await asyncio.to_thread(write_legacy_turn, workspace, issue='Z', turn='010_coder')
    early, _ = await asyncio.to_thread(write_legacy_turn, workspace, issue='A', turn='002_reviewer')
    rows = [receipt_row('same-operation', sequence=2), receipt_row('first', sequence=1),
            receipt_row('same-operation', sequence=3), receipt_row('not-successful', sequence=4, ok=False)]
    rows[0]['tool_invocation_manifest'] = {'control_plane_run_id': 'run-ref', 'control_plane_step_id': 'step-ref'}
    text = '\n{\nnull\n[]\n' + '\n'.join(json.dumps(row) for row in rows) + '\n'
    await asyncio.to_thread((directory / 'protocol_receipts.log').write_text, text, encoding='utf-8')
    await asyncio.to_thread((early / 'protocol_receipts.log').write_text,
                            json.dumps(receipt_row('earliest')) + '\n', encoding='utf-8')
    result = await observe(workspace, tmp_path)
    entries = result['narration_to_effect_audit']['entries']
    assert [row['operation_id'] for row in entries] == ['earliest', 'first', 'same-operation', 'same-operation']
    assert entries[0]['issue_id'] == 'A' and entries[0]['turn_index'] == 2 and entries[0]['role_name'] == 'reviewer'
    assert entries[2]['control_plane_run_id'] == 'run-ref' and entries[2]['control_plane_step_id'] == 'step-ref'
    assert 'control_plane_run_id' not in entries[3]
    assert result['narration_to_effect_audit']['verified_count'] == 4
    assert result['idempotency']['observed_surface_count'] == 3
    assert result['idempotency']['duplicate_operation_count'] == 1
    reused, = [row for row in result['idempotency']['surfaces'] if row['operation_id'] == 'same-operation']
    assert reused['dedupe_status'] == 'reused'


@pytest.mark.parametrize('kind', ['present', 'empty-file', 'directory', 'absent', 'outside', 'missing-path', 'failed'])
async def test_narration_file_audit_retains_existing_claim_ceiling(tmp_path, kind):
    workspace = tmp_path / 'workspace'
    directory, _ = await asyncio.to_thread(write_legacy_turn, workspace)
    artifact = workspace / 'agent_output/result.txt'
    path = 'agent_output/result.txt'
    if kind in {'directory', 'absent'}:
        await asyncio.to_thread(artifact.unlink)
        if kind == 'directory':
            await asyncio.to_thread(artifact.mkdir)
    elif kind == 'empty-file':
        await asyncio.to_thread(artifact.write_text, '', encoding='utf-8')
    elif kind == 'outside':
        outside = tmp_path / 'outside.txt'
        await asyncio.to_thread(outside.write_text, 'existing outside content', encoding='utf-8')
        path = str(outside)
    elif kind == 'missing-path':
        path = ''
    row = receipt_row('observed-write', path=path, ok=kind != 'failed')
    await asyncio.to_thread((directory / 'protocol_receipts.log').write_text, json.dumps(row), encoding='utf-8')
    result = await observe(workspace, tmp_path)
    if kind == 'failed':
        assert 'narration_to_effect_audit' not in result
        return
    entry, = result['narration_to_effect_audit']['entries']
    expected = {'present': 'none', 'empty-file': 'none', 'directory': 'workspace_artifact_missing',
                'absent': 'workspace_artifact_missing', 'outside': 'artifact_path_outside_workspace',
                'missing-path': 'artifact_path_missing'}[kind]
    assert entry['failure_reason'] == expected
    assert entry['audit_status'] == ('verified' if expected == 'none' else 'missing')
    assert result['narration_to_effect_audit']['verified_count'] == int(expected == 'none')
    assert result['narration_to_effect_audit']['missing_effect_count'] == int(expected != 'none')


@pytest.mark.parametrize('kind', ['absent-root', 'empty-root', 'invalid-legacy', 'missing-result'])
async def test_missing_receipt_evidence_never_invents_an_effect(tmp_path, kind):
    workspace = tmp_path / 'workspace'
    if kind == 'empty-root':
        await asyncio.to_thread((workspace / 'observability/run').mkdir, parents=True)
    elif kind in {'invalid-legacy', 'missing-result'}:
        directory, result_path = await asyncio.to_thread(write_legacy_turn, workspace)
        if kind == 'invalid-legacy':
            await asyncio.to_thread((directory / 'parsed_tool_calls.json').write_text, '{', encoding='utf-8')
        else:
            await asyncio.to_thread(result_path.unlink)
    result = await observe(workspace, tmp_path)
    assert 'narration_to_effect_audit' not in result and 'idempotency' not in result
