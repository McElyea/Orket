"""Local PRR command receipts; native Windows child ownership is retained."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger as write
from scripts.common.git_inventory import git_list_files
from orket.application.services.command_process_supervisor import CommandProcessSupervisor

BASE = ROOT / '.tmp/post-release-reliability'
EXTERNAL = Path('C:/Users/jonmc/AppData/Local/Temp/orket-prr-v1')
UV = Path('C:/Python314/Scripts/uv.exe')
PYTHONS = {'py311': Path('C:/Users/jonmc/AppData/Roaming/uv/python/cpython-3.11.14-windows-x86_64-none/python.exe'),
           'py312': Path('C:/Python312/python.exe')}
MODEL = 'orcarouter_qwen3.8-27b-uncensored-q4_k_l'
OPERATOR = 'model/core/rocks/run_the_business.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inventory():
    result = {p.relative_to(ROOT).as_posix(): sha(p) for p in git_list_files(ROOT)}
    result[OPERATOR] = hashlib.sha256(subprocess.check_output(['git', 'show', 'HEAD:' + OPERATOR], cwd=ROOT)).hexdigest()
    return result


def new_state(batch):
    directory = BASE / batch
    directory.mkdir(parents=True, exist_ok=False)
    state = dict(status='running', batch=batch, owner_pid=os.getpid(), started_at_unix=time.time(),
                 base_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                 source_sha256=inventory(), operator_sha256=sha(ROOT / OPERATOR), commands=[])
    write(directory / 'state.json', state)
    return directory, state


async def command(directory, state, args, label, cwd=ROOT, *, expected=0, seconds=600, extra_env=None, input_data=None):
    env = dict(os.environ, ORKET_DISABLE_SANDBOX='1', PYTHONUTF8='1', PYTHONUNBUFFERED='1',
               ORKET_PROVIDER_RUNTIME_AUTO_SELECT_MODEL='0', ORKET_PROVIDER_RUNTIME_AUTO_LOAD_LOCAL_MODEL='0')
    env.pop('PYTHONPATH', None)
    env.update(extra_env or {})
    row = dict(argv=[str(a) for a in args], cwd=str(cwd), status='running', started_at_unix=time.time(),
               deadline_seconds=seconds, environment_posture={'sandbox':'disabled','provider_switch':'disabled',
                   'model_auto_load':'disabled','pythonpath':'absent'})
    state['commands'].append(row)
    write(directory / 'state.json', state)
    print(json.dumps({'command':label,'status':'running'}), flush=True)
    owner = CommandProcessSupervisor(directory, cancellation_event='prr_command_interrupted')
    result = await owner.run(row['argv'], cwd=cwd, environment=env, timeout_seconds=seconds,
                             output_limit_bytes=16 * 1024 * 1024, input_data=input_data)
    row.update(status='finished', exit_code=result.returncode, lifetime=result.lifetime(), finished_at_unix=time.time())
    for stream, data in (('stdout', result.stdout), ('stderr', result.stderr)):
        log = directory / (label + '.' + stream + '.log')
        log.write_bytes(data)
        row[stream] = dict(path=str(log), sha256=sha(log))
    write(directory / 'state.json', state)
    print(json.dumps({'command':label,'exit_code':result.returncode,'cleanup':result.cleanup_confirmed}), flush=True)
    assert result.returncode == expected and result.reason == 'completed', row
    assert result.cleanup_confirmed and result.capture_complete, row
    return result


def finish(directory, state, result):
    state.update(status='finished', observed_result=result, finished_at_unix=time.time(),
                 source_inputs_unchanged=inventory() == state['source_sha256'])
    write(directory / 'state.json', state)
