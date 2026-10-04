"""Resume installed acceptance with preserved R02 package bytes."""
import asyncio
import json
import shutil
import sys
import uuid
import prr_common as p


async def startup(directory, state, python, cell, initialized):
    kind = 'initialized' if initialized else 'missing-board'
    project = p.EXTERNAL / (directory.name + '-' + cell + '-' + kind)
    project.mkdir()
    rock = project / 'model/core/rocks/run_the_business.json'
    if initialized:
        rock.parent.mkdir(parents=True)
        rock.write_text('{"name":"Run the Business","epics":[]}', encoding='utf-8')
        epic = project / 'model/core/epics/prr_startup.json'
        epic.parent.mkdir()
        epic.write_text('{"name":"prr_startup","team":"prr_team","environment":"standard","issues":[]}', encoding='utf-8')
        team = project / 'model/core/teams/prr_team.json'
        team.parent.mkdir()
        team.write_text('{"name":"PRR startup team","seats":{}}', encoding='utf-8')
    env = dict(ORKET_API_KEY=uuid.uuid4().hex, ORKET_DURABLE_ROOT=str(project / '.orket/durable'),
               ORKET_MODULE_PROFILE='developer-local', ORKET_GOVERNED_AGENT_SUPERVISOR_ENABLED='0',
               ORKET_LLM_PROVIDER='llama_cpp', ORKET_LLAMA_CPP_BASE_URL='http://127.0.0.1:8080/v1')
    result = await p.command(directory, state, [python.parent / 'orket.exe', 'runtime', '--workspace',
        project / 'workspace'], cell + '-' + kind, project, seconds=120, extra_env=env, input_data=b'exit\n')
    assert 'ORKET DRIVER (Interactive)' in result.stdout.decode('utf-8')
    warning = '[STARTUP WARNING] Structural reconciliation failed' in result.stderr.decode('utf-8')
    assert warning is not initialized
    if initialized:
        assert {'epic':'prr_startup','department':'core'} in json.loads(rock.read_text(encoding='utf-8'))['epics']
        assert '[Error:' not in result.stdout.decode('utf-8')
    state.setdefault('startup', []).append(dict(cell=cell, project=str(project), initialized=initialized,
        proof_mode='live', observed_path='primary' if initialized else 'degraded', observed_result='success',
        warning_present=warning, board_adoption_verified=initialized))
    p.write(directory / 'state.json', state)


async def main():
    directory, state = p.new_state(sys.argv[1] if len(sys.argv)>1 else 'installed-r03')
    candidate = p.BASE / 'candidate-r02'
    accepted = json.loads((candidate / 'state.json').read_text(encoding='utf-8'))
    state['artifacts'] = accepted['artifacts']
    for item in state['artifacts'].values():
        assert p.sha(item['path']) == item['sha256']
    failures = []
    result = 'failure'
    try:
        for cell, base in p.PYTHONS.items():
            env_dir = p.EXTERNAL / (directory.name + '-' + cell)
            await p.command(directory, state, [p.UV,'venv','--no-project','--seed','--no-python-downloads',
                '--python',base,env_dir], cell + '-venv', p.EXTERNAL)
            python = env_dir / 'Scripts/python.exe'
            await p.command(directory, state, [p.UV,'pip','install','--python',python,'--constraint',
                candidate / 'dependency-constraints.txt', *[item['path'] for item in state['artifacts'].values()]],
                cell + '-install', p.EXTERNAL)
            await p.command(directory, state, [python,'-m','pip','check'], cell + '-pip-check', p.EXTERNAL)
            for kind, script in [('journey','prr_journey.py'), ('turn-live','prr_turn_live.py')]:
                project = p.EXTERNAL / (directory.name + '-' + cell + '-' + kind)
                project.mkdir()
                shutil.copyfile(candidate / 'source/server.py', project / 'server.py')
                try:
                    await p.command(directory, state, [python,'-I',p.ROOT / '.tmp' / script,project,'0.7.2'],
                                    cell + '-' + kind, project, seconds=360)
                except AssertionError as error:
                    failures.append(dict(cell=cell, kind=kind, error=str(error)))
            for initialized in (False, True):
                try:
                    await startup(directory, state, python, cell, initialized)
                except AssertionError as error:
                    failures.append(dict(cell=cell, kind='startup', error=str(error)))
        state['failures'] = failures
        assert not failures, failures
        result = 'success'
    finally:
        p.finish(directory, state, result)


if __name__ == '__main__':
    asyncio.run(main())
