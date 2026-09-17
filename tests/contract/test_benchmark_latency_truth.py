"""Controlled duration records must not fabricate complete benchmark timing."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from scripts.benchmarks import render_benchmark_dashboard, report_benchmark_trends, score_benchmark_run


@pytest.fixture
def policy():
    return json.loads(Path('model/core/contracts/benchmark_scoring_policy.json').read_text(encoding='utf-8'))


def report(durations):
    return {'details': {'001': {'tier': 1, 'deterministic': True, 'unique_hashes': 1,
            'runs': [{'exit_code': 0, 'duration_ms': value} for value in durations]}}}


def score(durations, policy):
    return score_benchmark_run.score_report(report(durations), {'001': {'tier': 1}}, policy)


@pytest.mark.parametrize('durations,expected,status,count', [
    ([25.0, 75.0], 50.0, 'reported', 2), ([0.0, 0.0], 0.0, 'reported', 2),
    ([None, None], None, 'unavailable', 0), ([None, 50.0], None, 'partial', 1),
    ([], None, 'unavailable', 0), ([True, False], None, 'unavailable', 0),
    (['25', '75'], None, 'unavailable', 0), ([-1, 10], None, 'partial', 1),
    ([float('nan'), 10], None, 'partial', 1), ([float('inf'), 10], None, 'partial', 1),
    ([sys.float_info.max, sys.float_info.max], sys.float_info.max, 'reported', 2),
])
# Layer: contract
def test_only_complete_finite_duration_records_establish_an_average(policy, durations, expected, status, count):
    scored = score(durations, policy)
    assert scored['schema_version'] == 'v2'
    for level in (scored, scored['per_task_scores']['001']):
        assert level['avg_latency_ms'] == expected
        assert level['latency_summary'] == {
            'schema_version': 'benchmark_latency.v1', 'status': status, 'source': 'input_run.duration_ms',
            'samples_reported': count, 'runs_total': len(durations)}


# Layer: contract
def test_an_unmeasured_task_cannot_lower_the_overall_average(policy):
    payload = report([100.0])
    payload['details']['002'] = report([None])['details']['001']
    scored = score_benchmark_run.score_report(payload, {}, policy)
    assert scored['per_task_scores']['001']['avg_latency_ms'] == 100.0
    assert scored['avg_latency_ms'] is None and scored['latency_summary']['status'] == 'partial'


# Layer: contract
def test_legacy_scored_numbers_remain_visible_without_becoming_timing_evidence(tmp_path):
    inputs = []
    for index, duration in enumerate((40.0, 0.0)):
        path = tmp_path / f'{index}.json'
        path.write_text(json.dumps({'schema_version': 'v1', 'avg_latency_ms': duration}), encoding='utf-8')
        inputs.append(path)
    trends = report_benchmark_trends.build_trend_report(inputs)
    for row, duration in zip(trends['rows'], (40.0, 0.0), strict=True):
        assert row['legacy_avg_latency_ms'] == duration
        assert row['avg_latency_ms'] is None and row['delta_avg_latency_ms'] is None
        assert row['latency_summary']['status'] == 'legacy_unverified'
    rendered = render_benchmark_dashboard.build_dashboard_markdown(trends, {'groups': []})
    assert rendered.count('unavailable') >= 4


# Layer: contract
def test_partial_current_timing_has_no_trend_delta_and_does_not_render_as_zero(tmp_path, policy):
    inputs = []
    for index, durations in enumerate(([25.0, 75.0], [None, 50.0], [0.0, 0.0])):
        path = tmp_path / f'{index}.json'
        path.write_text(json.dumps(score(durations, policy)), encoding='utf-8')
        inputs.append(path)
    trends = report_benchmark_trends.build_trend_report(inputs)
    assert [row['avg_latency_ms'] for row in trends['rows']] == [50.0, None, 0.0]
    assert all(row['delta_avg_latency_ms'] is None for row in trends['rows'])
    rendered = render_benchmark_dashboard.build_dashboard_markdown(trends, {'groups': []})
    rows = [line.split('|') for line in rendered.splitlines() if line.startswith('| ') and '.json |' in line]
    assert [row[8].strip() for row in rows] == ['50.0', 'unavailable', '0.0']


@pytest.mark.parametrize('field,value', [('avg_latency_ms', -1), ('avg_latency_ms', float('inf')),
                                      ('status', 'measured'), ('samples_reported', True),
                                      ('runs_total', 3), ('source', 'invented')])
# Layer: contract
def test_current_summary_metadata_cannot_contradict_its_timing_value(tmp_path, policy, field, value):
    scored = score([25.0, 75.0], policy)
    target = scored if field == 'avg_latency_ms' else scored['latency_summary']
    target[field] = value
    path = tmp_path / 'scored.json'
    path.write_text(json.dumps(scored), encoding='utf-8')
    with pytest.raises(ValueError, match='E_BENCHMARK_LATENCY_SUMMARY_INVALID'):
        report_benchmark_trends.build_trend_report([path])


# Layer: contract
def test_nonobject_runs_fail_before_any_partial_scoring_can_escape(policy):
    payload = report([25.0])
    payload['details']['001']['runs'].append(None)
    with pytest.raises(ValueError, match='Benchmark runs must contain only JSON objects'):
        score_benchmark_run.score_report(payload, {}, policy)


@pytest.mark.parametrize('detail,message', [(None, 'Report task details must contain only JSON objects'),
                                          ({'runs': None}, 'Benchmark runs must be a JSON array')])
# Layer: contract
def test_malformed_task_inputs_cannot_disappear_from_duration_coverage(policy, detail, message):
    with pytest.raises(ValueError, match=message):
        score_benchmark_run.score_report({'details': {'001': detail}}, {}, policy)
