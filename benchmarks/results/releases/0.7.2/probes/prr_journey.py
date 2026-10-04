"""Installed public HTTP journey. Invoke with -I from the external project root."""
import asyncio
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import runpy
import socket
import sys
import uuid

ROOT = Path('C:/Source/Orket')
sys.path.insert(0, str(ROOT))
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger as write
sys.path.remove(str(ROOT))
import httpx
import uvicorn
import orket
import orket_extension_sdk as sdk

PROJECT = Path(sys.argv[1]).resolve()
VERSION = sys.argv[2]
MODEL = 'orcarouter_qwen3.8-27b-uncensored-q4_k_l'
SITE = (Path(sys.prefix) / 'Lib/site-packages').resolve()
KEY = uuid.uuid4().hex
ENV = dict(ORKET_DISABLE_SANDBOX='1', ORKET_STREAM_EVENTS_V1='true',
    ORKET_MODEL_STREAM_PROVIDER='real', ORKET_MODEL_STREAM_REAL_PROVIDER='llama_cpp',
    ORKET_MODEL_STREAM_REAL_MODEL_ID=MODEL, ORKET_MODEL_STREAM_OPENAI_USE_STREAM='true',
    ORKET_LLAMA_CPP_BASE_URL='http://127.0.0.1:8080/v1', ORKET_MODULE_PROFILE='developer-local',
    ORKET_PROVIDER_RUNTIME_AUTO_SELECT_MODEL='0', ORKET_PROVIDER_RUNTIME_AUTO_LOAD_LOCAL_MODEL='0',
    ORKET_MODEL_STREAM_REAL_TIMEOUT_S='120', ORKET_MODEL_STREAM_TURN_TIMEOUT_S='120',
    ORKET_GOVERNED_AGENT_SUPERVISOR_ENABLED='0', ORKET_DURABLE_ROOT=str(PROJECT / '.orket/durable'))
os.environ.update(ENV, ORKET_API_KEY=KEY)
assert Path.cwd() == PROJECT
assert not PROJECT.is_relative_to(ROOT)
assert Path(orket.__file__).resolve().is_relative_to(SITE)
assert Path(sdk.__file__).resolve().is_relative_to(SITE)
assert importlib.metadata.version('orket') == sdk.__version__ == VERSION
APP = runpy.run_path(str(PROJECT / 'server.py'))['app']
REPORT = dict(proof_mode='live', observed_path='primary', observed_result='failure',
    python=sys.version, version=VERSION, origins={'orket':orket.__file__,'sdk':sdk.__file__},
    environment=ENV, provider='llama_cpp', model=MODEL, project=str(PROJECT), turns=[])


async def json_request(client, method, path, payload=None):
    response = await client.request(method, path, json=payload)
    response.raise_for_status()
    return response.json()


async def turn(client, base, cancel, prompt=None):
    from websockets.asyncio.client import connect
    session = (await json_request(client, 'POST', '/v1/interactions/sessions', {}))['session_id']
    row = dict(session_id=session, cancel_requested=cancel, events=[])
    REPORT['turns'].append(row)
    async with connect(base.replace('http:', 'ws:') + '/ws/interactions/' + session,
                       additional_headers={'X-API-Key':KEY}) as websocket:
        config = {'model_id':MODEL, 'temperature':0, 'max_tokens':2048 if cancel else (512 if prompt else 96),
                  'prompt':prompt or ('List integers from 1 through 10000, each on its own line. Start now.' if cancel else
                            'Write one short sentence explaining why the sky appears blue.')}
        admitted = await json_request(client, 'POST', f'/v1/interactions/{session}/turns',
            {'workload_id':'model_stream_v1','input_config':config,'workspace':'workspace/default','turn_params':{}})
        row.update(admitted, input_config=config)
        while True:
            event = json.loads(await asyncio.wait_for(websocket.recv(), 130))
            row['events'].append(event)
            if cancel and event['event_type'] == 'token_delta' and 'cancel_ack' not in row:
                assert not event['payload'].get('synthetic') and event['payload']['delta']
                row['cancel_ack'] = await json_request(client, 'POST', f'/v1/interactions/{session}/cancel',
                                                       {'turn_id':admitted['turn_id']})
            if event['event_type'] == 'commit_final':
                break
    for view in ('status','snapshot','replay'):
        row[view] = await json_request(client, 'GET', f'/v1/sessions/{session}/{view}')
    kinds = [event['event_type'] for event in row['events']]
    assert 'token_delta' in kinds and 'stream_truncated' not in kinds, row
    assert kinds.count('turn_interrupted' if cancel else 'turn_final') == 1, row
    assert ('turn_final' if cancel else 'turn_interrupted') not in kinds, row
    assert row['events'][-1]['payload']['commit_outcome'] == 'ok', row
    assert not row['status']['active'], row
    if cancel:
        response = await client.post(f'/v1/interactions/{session}/cancel', json={'turn_id':admitted['turn_id']})
        row['terminal_cancel_status'] = response.status_code
        assert response.status_code == 409
    return row


async def parse_live_row(row, expect_violation):
    from datetime import datetime, timezone
    from orket.application.workflows.turn_response_parser import ResponseParser
    from orket.application.workflows.turn_response_capture import capture_turn_response
    from orket.application.workflows.turn_artifact_writer import TurnArtifactWriter
    from orket.application.workflows.turn_artifact_destination import TurnArtifactDestination
    from orket.application.workflows.turn_contract_validator import ContractValidator
    content = ''.join(event['payload']['delta'] for event in row['events'] if event['event_type']=='token_delta')
    destination = TurnArtifactDestination(TurnArtifactWriter(PROJECT), PROJECT, row['session_id'],
        'PRR-GROUNDING', 'developer', 'DEV', 1)
    parser = ResponseParser(utc_now=lambda:datetime.now(timezone.utc))
    parsed = await parser.parse_response(
        response=capture_turn_response({'content':content}), destination=destination, context={})
    diagnostics = ContractValidator(parser).hallucination_scope_diagnostics(parsed,
        {'verification_scope':{'strict_grounding':True,'declared_interfaces':['write_file']}})
    row['parser_proof'] = dict(content=content, content_sha256=hashlib.sha256(content.encode()).hexdigest(), diagnostics=diagnostics,
        tools=[{'tool':call.tool,'args':call.args} for call in parsed.tool_calls],
        artifact_directory=str(destination.output_dir), origin='actual non-synthetic public API token events')
    rules = [value['rule_id'] for value in diagnostics['violations']]
    assert rules == (['HALLUCINATION.INVENTED_DETAIL'] if expect_violation else []), row['parser_proof']
    assert parsed.tool_calls and all(call.tool == 'write_file' and call.args == {
        'path':'grounded.txt','content':'Maybe this should work.'} for call in parsed.tool_calls), row['parser_proof']


def durable_results():
    for row in REPORT['turns']:
        root = PROJECT / 'workspace/interactions' / row['session_id'] / row['turn_id']
        commit = json.loads((root / 'authority_commit.json').read_text(encoding='utf-8'))
        values = {name:commit[name] for name in ('session_id','turn_id','intents')}
        digest = hashlib.sha256(json.dumps(values, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        assert commit['authoritative'] and commit['commit_digest'] == digest
        if row['cancel_requested']:
            assert commit['intents'] == [{'type':'turn_finalize','ref':row['turn_id'],'payload_digest':None}]
            row['durable_semantics'] = 'interrupted lifecycle finalized; no model workload success intent'
        else:
            assert {'type':'turn_finalize','ref':'model_stream_v1','payload_digest':None} in commit['intents']
            row['durable_semantics'] = 'model workload completion intent; generated tokens are not a durable transcript'
        row['durable_commit'] = commit
        row['artifacts'] = {name:{'path':str(root / name),'sha256':hashlib.sha256((root / name).read_bytes()).hexdigest()}
                            for name in ('authority_commit.json','interaction_trace.jsonl')}


async def main():
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(APP, host='127.0.0.1', port=port, lifespan='on', log_level='info'))
    serving = asyncio.create_task(server.serve(sockets=[listener]))
    base = f'http://127.0.0.1:{port}'
    try:
        async with asyncio.timeout(30):
            while not server.started:
                if serving.done():
                    await serving
                    raise RuntimeError('Server exited before readiness')
                await asyncio.sleep(0.05)
        async with httpx.AsyncClient(base_url=base, headers={'X-API-Key':KEY}, trust_env=False, timeout=140) as client:
            REPORT['model_catalog'] = (await client.get('http://127.0.0.1:8080/v1/models')).json()
            assert MODEL in [item['id'] for item in REPORT['model_catalog']['data']]
            if '--upgrade-only' in sys.argv:
                session = (await json_request(client, 'POST', '/v1/interactions/sessions', {}))['session_id']
                response = await client.get('/ws/interactions/' + session, headers={
                    'Connection':'Upgrade','Upgrade':'websocket','Sec-WebSocket-Version':'13',
                    'Sec-WebSocket-Key':'dGhlIHNhbXBsZSBub25jZQ=='})
                REPORT['websocket_upgrade_status'] = response.status_code
                assert response.status_code == 101, f'WebSocket upgrade returned {response.status_code}: {response.text}'
            elif '--parser-proof' in sys.argv:
                tool_json = '{"tool":"write_file","args":{"path":"grounded.txt","content":"Maybe this should work."}}'
                for prefix in ('Maybe this should work. ',):
                    row = await turn(client, base, False,
                        'Repeat the following text exactly, including punctuation. No preamble, markdown or explanation. Text: ' + prefix + tool_json)
                    await parse_live_row(row, bool(prefix))
                REPORT['scope'] = 'live supported stream output to installed parser/validator; not a card TurnExecutor run'
            else:
                await turn(client, base, False)
                await turn(client, base, True)
    finally:
        server.should_exit = True
        await asyncio.wait_for(serving, 30)
        listener.close()
        runtime = APP.state.api_runtime_context
        REPORT['cleanup'] = dict(runtime_closed=runtime.closed, requests=runtime.active_request_count,
                                  background_tasks=runtime.active_background_task_count)
        assert runtime.closed and runtime.active_request_count == runtime.active_background_task_count == 0
    durable_results()
    REPORT['observed_result'] = 'success'


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except BaseException as error:
        REPORT['error'] = f'{type(error).__name__}: {error}'
        raise
    finally:
        write(PROJECT / 'journey.json', REPORT)
