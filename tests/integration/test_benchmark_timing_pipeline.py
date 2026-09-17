"""Native scoring/trend/dashboard commands retain unavailable duration semantics."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def write_input(folder, durations):
    runs = [{'exit_code': 0, 'hash': 'same', **({'duration_ms': value} if value is not None else {})}
            for value in durations]
    payload = {'details': {'001': {'tier': 1, 'deterministic': True, 'unique_hashes': 1, 'runs': runs}}}
    (folder / 'input.json').write_text(json.dumps(payload), encoding='utf-8')


def run_command(folder, name, *arguments):
    env = dict(os.environ, ORKET_DISABLE_SANDBOX='1')
    env.pop('PYTHONPATH', None)
    observed = subprocess.run([sys.executable, str(ROOT / 'scripts/benchmarks' / name), *arguments],
                              cwd=folder, env=env, capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert observed.returncode == 0, observed.stderr


def pipeline(folder):
    run_command(folder, 'score_benchmark_run.py', '--report', 'input.json', '--task-bank', 'tasks.json',
                '--policy', str(ROOT / 'model/core/contracts/benchmark_scoring_policy.json'), '--out', 'scored.json')
    run_command(folder, 'report_benchmark_trends.py', '--inputs', 'scored.json', '--out', 'trends.json')
    run_command(folder, 'render_benchmark_dashboard.py', '--trends', 'trends.json',
                '--leaderboard', 'leaderboard.json', '--out', 'dashboard.md')


@pytest.mark.parametrize('durations,expected,display', [([25.0, 75.0], 50.0, '50.0'),
                                                      ([None, None], None, 'unavailable'),
                                                      ([None, 50.0], None, 'unavailable'),
                                                      ([0.0, 0.0], 0.0, '0.0')])
# Layer: end-to-end
def test_native_pipeline_and_reruns_preserve_reported_duration_coverage(tmp_path, durations, expected, display):
    (tmp_path / 'tasks.json').write_text('[{"id":"001","tier":1}]', encoding='utf-8')
    (tmp_path / 'leaderboard.json').write_text('{"group_count":0,"groups":[]}', encoding='utf-8')
    write_input(tmp_path, durations)
    pipeline(tmp_path)
    scored = json.loads((tmp_path / 'scored.json').read_text(encoding='utf-8'))
    trend = json.loads((tmp_path / 'trends.json').read_text(encoding='utf-8'))['rows'][0]
    assert scored['avg_latency_ms'] == trend['avg_latency_ms'] == expected
    markdown = (tmp_path / 'dashboard.md').read_text(encoding='utf-8')
    line, = [row for row in markdown.splitlines() if row.startswith('| scored.json |')]
    assert line.split('|')[8].strip() == display
    assert scored['latency_summary']['runs_total'] == 2
    assert scored['latency_summary']['samples_reported'] == sum(value is not None for value in durations)
    write_input(tmp_path, [25.0, 75.0])
    pipeline(tmp_path)
    rerun = json.loads((tmp_path / 'scored.json').read_text(encoding='utf-8'))
    assert rerun['avg_latency_ms'] == 50.0
    assert len(rerun['diff_ledger']) == 2
    assert rerun['diff_ledger'][-1]['changed'] is (durations != [25.0, 75.0])
