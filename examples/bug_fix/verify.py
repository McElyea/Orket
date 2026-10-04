"""Frozen operator acceptance checks; this file is not a model-authored test."""
import io
import json
import os
import runpy
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent


def invoke(program, value):
    result = subprocess.run([sys.executable, '-I', '-B', str(program), json.dumps(value)],
                            capture_output=True, text=True, timeout=10, check=True)
    return json.loads(result.stdout)


def tests(program, names):
    os.environ['LABEL_PROGRAM'] = str(program)
    suite = unittest.TestSuite()
    for name in names:
        namespace = runpy.run_path(str(ROOT / name), run_name='verification_import')
        suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(SimpleNamespace(**namespace)))
    report = io.StringIO()
    result = unittest.TextTestRunner(stream=report).run(suite)
    if not result.wasSuccessful():
        print(report.getvalue(), file=sys.stderr)
    return result


def main():
    mode = sys.argv[1]
    if mode == 'case':
        return invoke(ROOT / 'main.py', json.loads(sys.argv[2]))
    if mode == 'reproduce':
        result = tests(ROOT / 'baseline.py', ['test_regression.py'])
        return {'baseline_rejected': bool(result.failures),
                'at_least_six_tests': result.testsRun >= 6, 'errors': len(result.errors)}
    result = tests(ROOT / 'main.py', ['test_existing.py', 'test_regression.py'])
    passed = result.wasSuccessful() and result.testsRun >= 8
    if mode == 'tests':
        return {'tests_passed': passed, 'at_least_eight_tests': result.testsRun >= 8}
    if mode == 'review':
        review = json.loads((ROOT / 'review.json').read_text(encoding='utf-8'))
        return {'tests_passed': passed, 'review_matches': review == {
            'bug': 'whitespace-normalization', 'status': 'reviewed',
            'scope': 'declared-cases-only', 'changed_file': 'agent_output/main.py'}}
    raise ValueError('Unknown verification mode: ' + mode)


if __name__ == '__main__':
    print(json.dumps(main(), ensure_ascii=True))
