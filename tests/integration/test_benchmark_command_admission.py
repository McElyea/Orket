"""Native benchmark commands refuse unsupported or unmeasured admission."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def run_script(folder, script, *arguments):
    env = dict(os.environ, ORKET_DISABLE_SANDBOX='1')
    env.pop('PYTHONPATH', None)
    env['PATH'] = str(Path(sys.executable).parent) + os.pathsep + env.get('PATH', '')
    return subprocess.run([sys.executable, str(ROOT / 'scripts/benchmarks' / script), *arguments],
                          cwd=folder, env=env, capture_output=True, text=True, encoding='utf-8', timeout=25)


def runner(folder):
    path = folder / 'runner.py'
    path.write_text("from pathlib import Path\nPath(__file__).with_suffix('.started').touch()\nprint('ok')\n", encoding='utf-8')
    return f'python {path.as_posix()}'


@pytest.mark.parametrize('tasks,runs,extra,error', [
    ([], '2', [], 'E_BENCHMARK_TASK_SET_EMPTY'),
    ([{'id': '001'}], '0', [], 'E_BENCHMARK_RUN_COUNT_INVALID'),
    ([{'id': '001'}], '-1', [], 'E_BENCHMARK_RUN_COUNT_INVALID'),
    ([{'id': '001'}], '2', ['--task-id-min', '2'], 'E_BENCHMARK_TASK_SET_EMPTY'),
    ([{'id': '001'}, {'id': '001'}], '2', [], 'E_BENCHMARK_TASK_ID_DUPLICATE'),
    ([None], '2', [], 'E_BENCHMARK_TASK_INVALID'),
    ({}, '2', [], 'E_BENCHMARK_TASK_BANK_INVALID'),
    ([{'id': True}], '2', [], 'E_BENCHMARK_TASK_INVALID'),
    ([{'id': ' '}], '2', [], 'E_BENCHMARK_TASK_INVALID'),
    ([{'id': '001'}], '2', ['--task-id-min', '3', '--task-id-max', '2'], 'E_BENCHMARK_TASK_FILTER_INVALID'),
    ([{'id': '001'}], '2', ['--runner-template', ' '], 'E_BENCHMARK_RUNNER_REQUIRED'),
])
# Layer: integration
def test_invalid_harness_admission_does_not_launch_or_replace_a_report(tmp_path, tasks, runs, extra, error):
    (tmp_path / 'tasks.json').write_text(json.dumps(tasks), encoding='utf-8')
    output = tmp_path / 'report.json'
    output.write_bytes(b'previous retained report')
    observed = run_script(tmp_path, 'run_determinism_harness.py', '--task-bank', 'tasks.json',
                          '--runs', runs, '--runner-template', runner(tmp_path), '--output', 'report.json', *extra)
    assert observed.returncode == 2 and error in observed.stderr
    assert not (tmp_path / 'runner.started').exists()
    assert output.read_bytes() == b'previous retained report'


# Layer: integration
def test_harness_requires_an_explicit_runner_template(tmp_path):
    (tmp_path / 'tasks.json').write_text('[{"id":"001"}]', encoding='utf-8')
    observed = run_script(tmp_path, 'run_determinism_harness.py', '--task-bank', 'tasks.json', '--output', 'report.json')
    assert observed.returncode == 2 and '--runner-template' in observed.stderr
    assert not (tmp_path / 'report.json').exists()


# Layer: integration
def test_valid_harness_executes_real_runner_and_preserves_rerun_history(tmp_path):
    (tmp_path / 'tasks.json').write_text('[{"id":"001"}]', encoding='utf-8')
    template = runner(tmp_path)
    for _ in range(2):
        observed = run_script(tmp_path, 'run_determinism_harness.py', '--task-bank', 'tasks.json', '--runs', '1',
                              '--runner-template', template, '--output', 'report.json')
        assert observed.returncode == 0, observed.stderr
    payload = json.loads((tmp_path / 'report.json').read_text(encoding='utf-8'))
    assert (tmp_path / 'runner.started').exists()
    assert len(payload['test_runs']) == 1 and payload['avg_latency_ms'] > 0
    assert len(payload['diff_ledger']) == 2 and payload['details']['001']['deterministic'] is None


def selector_input(folder, row):
    (folder / 'input.json').write_text(json.dumps({'sessions': [{'model_id': 'controlled', 'per_quant': [row]}]}), encoding='utf-8')


@pytest.mark.parametrize('latency', [None, True, -1, '0', float('nan'), float('inf')])
# Layer: integration
def test_missing_or_invalid_latency_cannot_qualify_for_the_selector(tmp_path, latency):
    row = {'valid': True, 'adherence_score': 1.0, 'quant_tag': 'Q4'}
    if latency is not None:
        row['total_latency'] = latency
    selector_input(tmp_path, row)
    observed = run_script(tmp_path, 'prototype_model_selector.py', '--summary', 'input.json',
                          '--max-latency', '0.01', '--out', 'report.json')
    assert observed.returncode == 0, observed.stderr
    payload = json.loads((tmp_path / 'report.json').read_text(encoding='utf-8'))
    assert payload['schema_version'] == 'selector.prototype.v2'
    assert payload['selected'] is None and payload['candidate_count'] == 0
    assert payload['rejected_candidates'][0]['reason'] == 'latency_unavailable'


@pytest.mark.parametrize('arguments', [('--max-latency', 'nan'), ('--max-latency', 'inf'), ('--max-latency', '-1'),
                                     ('--min-adherence', 'nan'), ('--min-adherence', '1.1')])
# Layer: integration
def test_invalid_selector_policy_refuses_before_replacing_a_report(tmp_path, arguments):
    selector_input(tmp_path, {'valid': True, 'adherence_score': 1.0, 'total_latency': 1.0})
    (tmp_path / 'report.json').write_bytes(b'previous retained report')
    observed = run_script(tmp_path, 'prototype_model_selector.py', '--summary', 'input.json', '--out', 'report.json', *arguments)
    assert observed.returncode == 2 and 'E_MODEL_SELECTOR_POLICY_INVALID' in observed.stderr
    assert (tmp_path / 'report.json').read_bytes() == b'previous retained report'


# Layer: integration
def test_reported_zero_is_distinct_from_missing_and_selector_reruns_retain_history(tmp_path):
    row = {'valid': True, 'adherence_score': 1.0, 'total_latency': 0.0, 'quant_tag': 'Q4'}
    selector_input(tmp_path, row)
    observed = run_script(tmp_path, 'prototype_model_selector.py', '--summary', 'input.json', '--out', 'report.json')
    assert observed.returncode == 0, observed.stderr
    payload = json.loads((tmp_path / 'report.json').read_text(encoding='utf-8'))
    assert payload['selected']['total_latency'] == 0.0 and payload['candidate_count'] == 1
    row.pop('total_latency')
    selector_input(tmp_path, row)
    observed = run_script(tmp_path, 'prototype_model_selector.py', '--summary', 'input.json', '--out', 'report.json')
    assert observed.returncode == 0, observed.stderr
    payload = json.loads((tmp_path / 'report.json').read_text(encoding='utf-8'))
    assert payload['selected'] is None and len(payload['diff_ledger']) == 2


@pytest.mark.parametrize('change,reason', [
    ({'valid': 'true'}, 'run_not_valid'),
    ({'valid': 1}, 'run_not_valid'),
    ({'adherence_score': None}, 'adherence_unavailable'),
    ({'adherence_score': 1.1}, 'adherence_unavailable'),
    ({'adherence_score': 0.5}, 'adherence_below_minimum'),
    ({'total_latency': 11}, 'latency_above_maximum'),
    ({'total_latency': 5e-324}, 'utility_unrepresentable'),
])
# Layer: integration
def test_selector_explains_rejected_candidate_evidence(tmp_path, change, reason):
    selector_input(tmp_path, {'valid': True, 'adherence_score': 1.0, 'total_latency': 1.0, 'quant_tag': 'Q4', **change})
    observed = run_script(tmp_path, 'prototype_model_selector.py', '--summary', 'input.json', '--out', 'report.json')
    assert observed.returncode == 0, observed.stderr
    payload = json.loads((tmp_path / 'report.json').read_text(encoding='utf-8'))
    assert payload['selected'] is None and payload['candidate_count'] == 0
    assert payload['rejected_candidates'][0]['reason'] == reason
    assert payload['measurement_posture'] == 'reported_unverified'


@pytest.mark.parametrize('summary', [
    {}, {'sessions': [None]}, {'sessions': [{'model_id': '', 'per_quant': []}]},
    {'sessions': [{'model_id': 'controlled', 'per_quant': [None]}]},
])
# Layer: integration
def test_malformed_selector_summary_preserves_previous_report(tmp_path, summary):
    (tmp_path / 'input.json').write_text(json.dumps(summary), encoding='utf-8')
    (tmp_path / 'report.json').write_bytes(b'previous retained report')
    observed = run_script(tmp_path, 'prototype_model_selector.py', '--summary', 'input.json', '--out', 'report.json')
    assert observed.returncode != 0 and 'E_MODEL_SELECTOR_' in observed.stderr
    assert (tmp_path / 'report.json').read_bytes() == b'previous retained report'
