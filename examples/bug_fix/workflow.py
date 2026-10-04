"""Four reusable card stages with task-specific, operator-declared acceptance."""
import json

CASES = [
    ('basic', 'Hello World', 'hello-world'),
    ('empty', '', ''),
    ('padding', '  Hello World  ', 'hello-world'),
    ('repeated', 'Alpha   Beta', 'alpha-beta'),
    ('tabs', 'Alpha\tBeta', 'alpha-beta'),
    ('newlines', 'Alpha\nBeta', 'alpha-beta'),
    ('whitespace-only', ' \t\n ', ''),
    ('unicode', 'CAFÉ\u2003MÜNCHEN', 'café-münchen'),
    ('punctuation', '  Build_v2: OK!  ', 'build_v2:-ok!'),
]
COMMON = ['agent_output/verify.py', 'agent_output/main.py']
TESTS = COMMON + ['agent_output/test_existing.py', 'agent_output/test_regression.py']


def acceptance(issue_id, paths, cases):
    return {'schema_version': 'card_python_cli_acceptance.v1',
            'acceptance_ref': issue_id + '.acceptance.v1', 'policy_ref': 'label-normalization.v1',
            'workload_id': issue_id, 'entrypoint': 'agent_output/verify.py',
            'artifact_paths': paths, 'timeout_seconds': 30,
            'cases': [{'criterion_id': name, 'description': name, 'arguments': arguments,
                       'expected_json': json.dumps(expected)} for name, arguments, expected in cases]}


def card(issue_id, summary, seat, note, reads, writes, definition, previous=None):
    primary = writes[0] if writes else 'agent_output/main.py'
    return {'id': issue_id, 'summary': summary, 'seat': seat, 'priority': 'High', 'status': 'ready',
            'depends_on': [previous] if previous else [], 'note': note,
            'params': {'completion_acceptance': definition, 'cards_runtime': {
                'execution_profile': 'write_artifact_v1',
                'artifact_contract': {'kind': 'artifact', 'primary_output': primary,
                    'required_read_paths': reads, 'required_write_paths': writes,
                    'review_read_paths': list(dict.fromkeys(reads + writes))}},
                'turn_contract': {'required_action_tools': (['write_file'] if writes else []) + ['update_issue_status'],
                    'required_read_paths': reads, 'required_write_paths': writes,
                    'required_statuses': ['code_review']}}}


def epic(model):
    instructions = ('Read the required files, make only the requested changes, then use '
                    'update_issue_status with code_review. The runtime executes declared acceptance; '
                    'do not invent test results. Do not modify verify.py, baseline.py, test_existing.py or requirements.txt. ')
    regression = card('BF-01', 'Reproduce the whitespace bug with regression tests', 'coder', instructions +
        'Write agent_output/test_regression.py using unittest.TestCase. Define at least six test_ methods for '
        'padding, repeated spaces, tabs, newlines, whitespace-only input and Unicode whitespace. '
        'Each test must execute the real CLI with subprocess.run([sys.executable, os.environ["LABEL_PROGRAM"], '
        'json.dumps(input)], check=True, capture_output=True, text=True, timeout=10), parse stdout as JSON '
        'and assert the expected normalized string. Follow test_existing.py. No external dependencies. '
        'Use a module docstring declaring Layer: end-to-end. The frozen verifier supplies LABEL_PROGRAM '
        'and imports the file without executing a __main__ block. Do not repair main.py on this card.',
        ['agent_output/requirements.txt', 'agent_output/main.py', 'agent_output/test_existing.py'],
        ['agent_output/test_regression.py'], acceptance('BF-01',
            ['agent_output/verify.py', 'agent_output/baseline.py', 'agent_output/test_regression.py'],
            [('reproduction', ['reproduce'], {'baseline_rejected': True, 'at_least_six_tests': True, 'errors': 0})]))
    repair = card('BF-02', 'Fix label normalization without changing the public CLI', 'coder', instructions +
        'Repair normalize_label in agent_output/main.py. Preserve the function and JSON-in/JSON-out CLI. '
        'Handle all Unicode whitespace, collapse runs to one hyphen, trim outer whitespace and lowercase; '
        'preserve non-whitespace punctuation. Implement the general behavior, not a lookup table.',
        ['agent_output/requirements.txt', 'agent_output/main.py', 'agent_output/test_regression.py'],
        ['agent_output/main.py'], acceptance('BF-02', COMMON,
            [(name, ['case', json.dumps(value)], expected) for name, value, expected in CASES]), 'BF-01')
    verify = card('BF-03', 'Run existing and new regression tests through acceptance', 'code_reviewer', instructions +
        'Read the implementation and both test files. Request code_review after inspection. '
        'The completion verifier runs the actual existing and regression test suites before accepting this card. '
        'You have no shell tool; do not claim to have run a command yourself.',
        ['agent_output/main.py', 'agent_output/test_existing.py', 'agent_output/test_regression.py'], [],
        acceptance('BF-03', TESTS, [('tests', ['tests'], {'tests_passed': True, 'at_least_eight_tests': True})]), 'BF-02')
    review = card('BF-04', 'Review the fix and leave an inspectable handoff', 'coder', instructions +
        'Inspect the implementation and regression suite. Write agent_output/review.json exactly as the JSON object '
        '{"bug":"whitespace-normalization","status":"reviewed","scope":"declared-cases-only",'
        '"changed_file":"agent_output/main.py"}. This records a review decision; the runtime independently '
        'requires the test suite to pass before accepting it.',
        ['agent_output/requirements.txt', 'agent_output/main.py', 'agent_output/test_regression.py'],
        ['agent_output/review.json'], acceptance('BF-04', TESTS + ['agent_output/review.json'],
            [('review', ['review'], {'tests_passed': True, 'review_matches': True})]), 'BF-03')
    return {'id': 'bug_fix', 'name': 'Whitespace normalization bug fix', 'type': 'epic',
            'description': 'Seeded small Python repository; four real model-backed card stages.',
            'team': 'bug_fix', 'environment': 'standard',
            'architecture_governance': {'idesign': False, 'pattern': 'Tactical'},
            'params': {'model_overrides': {role: model for role in ('coder', 'code_reviewer', 'integrity_guard')}},
            'issues': [regression, repair, verify, review]}
