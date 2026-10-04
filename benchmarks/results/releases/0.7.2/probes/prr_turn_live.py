"""Installed actual-provider turn execution and parser grounding observations."""
import asyncio
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys

SOURCE = Path('C:/Source/Orket')
sys.path.insert(0, str(SOURCE))
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger as write
sys.path.remove(str(SOURCE))
import orket
from orket.application.services.local_model_factory import create_local_model_provider_async
from orket.application.services.tool_gate_service import ToolGate
from orket.application.services.toolbox import ToolBox
from orket.application.workflows.turn_executor import TurnExecutor
from orket.application.workflows.turn_artifact_destination import TurnArtifactDestination
from orket.application.workflows.turn_response_capture import capture_turn_response
from orket.core.contracts.logging_inputs import LoggingInputs
from orket.core.domain.state_machine import StateMachine
from orket.logging import bind_logging, prepare_logging
from orket.schema import CardStatus, IssueConfig, RoleConfig
from orket.settings import set_runtime_settings_context

PROJECT = Path(sys.argv[1]).resolve()
MODEL = 'orcarouter_qwen3.8-27b-uncensored-q4_k_l'
assert Path.cwd() == PROJECT and not PROJECT.is_relative_to(SOURCE)
assert Path(orket.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
assert importlib.metadata.version('orket') == '0.7.2'
os.environ.update(ORKET_DISABLE_SANDBOX='1', ORKET_LLM_PROVIDER='llama_cpp',
    ORKET_LLAMA_CPP_BASE_URL='http://127.0.0.1:8080/v1',
    ORKET_LLM_LLAMA_CPP_BASE_URL='http://127.0.0.1:8080/v1',
    ORKET_PROVIDER_RUNTIME_AUTO_SELECT_MODEL='0', ORKET_PROVIDER_RUNTIME_AUTO_LOAD_LOCAL_MODEL='0',
    ORKET_DURABLE_ROOT=str(PROJECT / '.orket/durable'))
set_runtime_settings_context(user_settings={}, user_preferences={})
WORKSPACE = PROJECT / 'workspace'
WORKSPACE.mkdir()
GATE = ToolGate(organization=None, workspace_root=WORKSPACE)
TOOLBOX = ToolBox(policy=None, workspace_root=str(WORKSPACE), references=[], tool_gate=GATE)
EXECUTOR = TurnExecutor(StateMachine(), GATE, WORKSPACE, utc_now=lambda:datetime.now(timezone.utc))
REPORT = dict(proof_mode='live', observed_path='primary', observed_result='failure',
              python=sys.version, provider='llama_cpp', model=MODEL, origin=orket.__file__)


async def main():
    with bind_logging(await prepare_logging(LoggingInputs(WORKSPACE))):
        async with (await create_local_model_provider_async(model=MODEL, provider='llama_cpp',
                    base_url='http://127.0.0.1:8080/v1', temperature=0, seed=7, timeout=120)) as provider:
            issue = IssueConfig(id='PRR-LIVE', summary='Write the requested file',
                description='Write grounded.txt with exactly PRR live grounding accepted followed by a newline.',
                seat='developer', status=CardStatus.IN_PROGRESS)
            role = RoleConfig(id='DEV', summary='developer', description='Write the requested file.', tools=['write_file'])
            context = dict(session_id='prr-live-turn', issue_id=issue.id, role='developer', roles=['developer'],
                current_status='in_progress', selected_model=MODEL, turn_index=1, history=[],
                required_action_tools=['write_file'], required_write_paths=['grounded.txt'],
                verification_scope={'strict_grounding':True,'declared_interfaces':['write_file']})
            result = await EXECUTOR.execute_turn(issue, role, provider, TOOLBOX, context,
                system_prompt='Return only JSON tool calls. Use {"tool":"write_file","args":{"path":"grounded.txt",'
                    '"content":"PRR live grounding accepted\\n"}} exactly. No commentary or markdown.')
            REPORT['turn'] = {'success':result.success,'error':result.error,
                             'content':result.turn.content if result.turn else None}
            assert result.success, result.error
            artifact = WORKSPACE / 'grounded.txt'
            content = await asyncio.to_thread(artifact.read_bytes)
            assert content == b'PRR live grounding accepted\r\n', content
            REPORT['output'] = dict(path=str(artifact), sha256=hashlib.sha256(content).hexdigest(),
                bytes_hex=content.hex(), newline_semantics='existing Windows text-mode write translates newline to CRLF')
            response = await provider.complete([
                {'role':'system','content':'Repeat the requested text literally, with no JSON, explanation or thinking.'},
                {'role':'user','content':'Repeat exactly: Maybe this should work.'}])
            REPORT['grounding_response'] = response.content
            assert 'Maybe this' in response.content, response.content
            destination = TurnArtifactDestination(writer=EXECUTOR.artifact_writer, workspace=WORKSPACE,
                session_id='prr-live-grounding',issue_id='PRR-GROUNDING',role_name='developer',role_id='DEV',turn_index=1)
            parsed = await EXECUTOR.response_parser.parse_response(response=capture_turn_response(response),
                                                                   destination=destination, context={})
            diagnostics = EXECUTOR.contract_validator.hallucination_scope_diagnostics(parsed,
                {'verification_scope':{'strict_grounding':True}})
            REPORT['grounding_diagnostics'] = diagnostics
            assert [row['rule_id'] for row in diagnostics['violations']] == ['HALLUCINATION.INVENTED_DETAIL']
        REPORT['provider_client_closed'] = provider.client.is_closed
        assert provider.client.is_closed
    REPORT['observed_result'] = 'success'


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except BaseException as error:
        REPORT['error'] = f'{type(error).__name__}: {error}'
        raise
    finally:
        write(PROJECT / 'turn-live.json', REPORT)
