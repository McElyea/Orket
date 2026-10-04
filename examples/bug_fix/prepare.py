"""Create a new isolated bug-fix project; refuse to overwrite an existing path."""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

from workflow import epic

# Direct invocation needs the checkout's validation and receipt-writing helpers.
SOURCE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SOURCE))
from orket.core.contracts.card_acceptance_inputs import PythonCliAcceptance  # noqa: E402
from orket.core.contracts.provider_runtime import DEFAULT_LOCAL_MODEL  # noqa: E402
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger  # noqa: E402

REQUIREMENTS = '''normalize_label accepts a string and returns its lowercase words joined by one hyphen.
Leading/trailing whitespace is removed. All Unicode whitespace separates words.
Repeated whitespace collapses to one separator. Empty or whitespace-only input returns an empty string.
Preserve all non-whitespace punctuation and characters apart from lowercasing.
CLI: python agent_output/main.py <JSON-encoded-string>; stdout is one JSON string.
Keep the function normalize_label and the CLI interface. Use the Python standard library only.
The original implementation deliberately mishandles repeated and non-space whitespace.
The task is to add regression tests, repair it, pass existing/new tests, and review the fix.
The frozen operator verifier and original baseline are not model-editable task inputs.
'''


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')


def prepare(project, model):
    project.mkdir(parents=True, exist_ok=False)
    output = project / 'workspace/agent_output'
    output.mkdir(parents=True)
    source = Path(__file__).resolve().parent
    for name in ('main.py', 'test_existing.py'):
        shutil.copyfile(source / 'seed' / name, output / name)
    shutil.copyfile(source / 'seed/main.py', output / 'baseline.py')
    shutil.copyfile(source / 'verify.py', output / 'verify.py')
    (output / 'requirements.txt').write_text(REQUIREMENTS, encoding='utf-8')
    write_json(project / 'config/organization.json', {
        'name': 'Bug Fix Demo', 'vision': 'One verified local repair', 'ethos': 'Truthful outcomes',
        'branding': {'design_dos': []}, 'departments': ['core'],
        'architecture': {'cicd_rules': [], 'preferred_stack': {}, 'idesign_threshold': 7},
        'process_rules': {'disable_runtime_verifier': True}})
    write_json(project / 'model/core/environments/standard.json', {
        'name': 'standard', 'model': model, 'temperature': 0, 'timeout': 120})
    descriptions = {
        'coder': 'Implement the current card only. Read required inputs and persist requested files. '
                 'Finish by setting code_review. Emit JSON tool calls without speculative prose.',
        'code_reviewer': 'Read the current card inputs and implementation. Set code_review to request '
                         'mechanical verification. Do not invent test results.',
        'integrity_guard': 'Read the required artifacts and acceptance diagnostics. Finalize done only when '
                           'the declared acceptance is satisfied; otherwise block. Emit JSON tool calls.'}
    for role, description in descriptions.items():
        original = json.loads((SOURCE / 'model/core/roles' / (role + '.json')).read_text(encoding='utf-8'))
        original['description'] = description
        original['tools'] = ['read_file', 'update_issue_status'] + (['write_file'] if role == 'coder' else [])
        write_json(project / 'model/core/roles' / (role + '.json'), original)
    write_json(project / 'model/core/teams/bug_fix.json', {'name': 'bug_fix', 'seats': {
        role: {'name': role, 'roles': [role]} for role in descriptions}})
    for dialect in ('qwen', 'generic'):
        write_json(project / 'model/core/dialects' / (dialect + '.json'), {
            'model_family': dialect, 'dsl_format': 'JSON', 'constraints': [], 'hallucination_guard': 'None'})
    write_json(project / 'model/core/rocks/run_the_business.json', {'name': 'Bug Fix Demo', 'epics': []})
    definition = epic(model)
    for issue in definition['issues']:
        PythonCliAcceptance.model_validate(issue['params']['completion_acceptance'])
    write_json(project / 'model/core/epics/bug_fix.json', definition)
    write_json(project / '.orket/durable/config/user_settings.json', {'module_profile': 'developer-local'})
    write_json(project / '.orket/durable/config/user_preferences.json', {})
    receipt = {'project': str(project), 'provider': 'llama_cpp', 'model': model, 'seeded_bug': True,
               'observed_path': 'primary', 'observed_result': 'success',
               'files_sha256': {p.relative_to(project).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in sorted(project.rglob('*')) if p.is_file()},
               'scope': 'Setup only; no model execution or acceptance implied.'}
    write_payload_with_diff_ledger(project / 'setup.json', receipt)
    print(json.dumps({'project': str(project), 'card_ids': [i['id'] for i in definition['issues']]}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project', type=Path)
    parser.add_argument('--model', default=DEFAULT_LOCAL_MODEL)
    arguments = parser.parse_args()
    prepare(arguments.project.resolve(), arguments.model)
