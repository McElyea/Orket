"""Scoped PRR release gates and paired installed SDK validation."""
import asyncio
import json
import sys
import prr_common as p
from release_070_verify import SELECTION

PARSER = ['tests/application/test_turn_response_parser.py','tests/application/test_turn_contract_validator.py',
    'tests/application/test_turn_contract_rule_admission.py','tests/application/test_turn_executor_middleware.py',
    'tests/integration/test_turn_response_parser_admission.py','tests/integration/test_turn_parser_publication_ownership.py',
    'tests/runtime/test_protocol_error_code_adoption.py']
SOCKET = ['tests/integration/test_api_websocket_disconnect.py','tests/integration/test_api_captured_websocket_inputs.py',
    'tests/interfaces/test_api_interactions.py','tests/integration/test_interaction_subscription_lifetime.py',
    'tests/integration/test_api_interaction_lifetime.py','tests/integration/test_api_interaction_cancellation.py',
    'tests/integration/test_interaction_cancel_ownership.py','tests/integration/test_interaction_artifact_ownership.py']
STREAM = [str(path.relative_to(p.ROOT)) for path in sorted((p.ROOT/'tests/integration').glob('test_model_stream_*.py'))]
OTHERS = ['tests/integration/test_runtime_project_roots.py','tests/integration/test_application_root_inputs.py',
    'tests/e2e/test_packaged_extension_scaffold.py','tests/scripts/test_current_authority_source.py',
    'tests/platform/test_current_authority_map.py','tests/platform/test_remediation_authority_docs.py']


async def main():
    directory,state=p.new_state('verification')
    candidate=p.BASE/'candidate-r02'
    artifacts=json.loads((candidate/'state.json').read_text())['artifacts']
    constraints=candidate/'dependency-constraints.txt'
    result='failure'
    failures=[]
    try:
        for cell,base in p.PYTHONS.items():
            env=p.EXTERNAL/('verification-'+cell)
            await p.command(directory,state,[p.UV,'venv','--no-project','--seed','--no-python-downloads',
                '--python',base,env],cell+'-venv',p.EXTERNAL)
            python=env/'Scripts/python.exe'
            await p.command(directory,state,[python,'-m','pip','install','--constraint',constraints,
                artifacts['orket']['path']+'[dev]',artifacts['orket_extension_sdk']['path']],cell+'-install',p.EXTERNAL)
            await p.command(directory,state,[python,'-m','pip','check'],cell+'-pip-check',p.EXTERNAL)
            selection=list(dict.fromkeys(SELECTION+PARSER+SOCKET+STREAM+OTHERS)) if cell=='py311' else ['tests/e2e/test_packaged_extension_scaffold.py']
            try:
                await p.command(directory,state,[python,'-m','pytest','-q',*selection,'--tb=short',
                    '--junitxml='+str(directory/(cell+'-controls.xml')),'--basetemp='+str(directory/(cell+'-pytest-temp'))],
                    cell+'-controls',seconds=900)
            except AssertionError:
                failures.append(cell+'-controls')
        python=p.EXTERNAL/'verification-py311/Scripts/python.exe'
        for label,args in [('ruff',['-m','ruff','check','orket','tests','orket_extension_sdk']),
            ('mypy',['-m','mypy','orket/','--ignore-missing-imports']),
            ('dependency',['scripts/governance/check_dependency_direction.py']),
            ('taxonomy',['scripts/governance/enforce_test_taxonomy.py','--strict']),
            ('noop',['scripts/governance/check_noop_critical_paths.py'])]:
            try:
                await p.command(directory,state,[python,*args],label,seconds=900)
            except AssertionError:
                failures.append(label)
        env=p.EXTERNAL/'verification-sdk-only'
        await p.command(directory,state,[p.UV,'venv','--no-project','--seed','--no-python-downloads',
            '--python',p.PYTHONS['py311'],env],'sdk-only-venv',p.EXTERNAL)
        python=env/'Scripts/python.exe'
        await p.command(directory,state,[python,'-m','pip','install','--constraint',constraints,
            artifacts['orket_extension_sdk']['path']],'sdk-only-install',p.EXTERNAL)
        code='import importlib.util,importlib.metadata,json,sys;import orket_extension_sdk as sdk;from pathlib import Path;assert sdk.__version__==importlib.metadata.version("orket-extension-sdk")=="0.7.2";assert importlib.util.find_spec("orket") is None;assert Path(sdk.__file__).is_relative_to(Path(sys.prefix)/"Lib/site-packages");print(json.dumps({"version":sdk.__version__,"origin":sdk.__file__,"host_namespace_absent":True}))'
        await p.command(directory,state,[python,'-I','-c',code],'sdk-only-import',p.EXTERNAL)
        await p.command(directory,state,[python,'-m','pip','check'],'sdk-only-pip-check',p.EXTERNAL)
        state['failures']=failures
        assert not failures,failures
        result='success'
    finally:
        p.finish(directory,state,result)


asyncio.run(main())
