"""Contract proof for bounded outside-package import-name analysis."""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers.dependency_repository import make_repository, run_command

pytestmark = pytest.mark.contract

VALIDATOR = (
    'def external_name(name):\n'
    '    if type(name) is not str:\n'
    '        raise TypeError()\n'
    "    if name == 'orket' or name.startswith('orket.'):\n"
    '        raise ValueError()\n'
    "    if name.startswith('.'):\n"
    '        raise ValueError()\n'
    '    return name\n'
)


def _files(body: str, *, validator: str = VALIDATOR, imported: bool = False) -> dict[str, str]:
    header = 'from orket.adapters.validation import external_name\n' if imported else validator
    files = {'orket/adapters/source.py': 'import importlib, sys\n' + header + 'def load(value):\n' + body}
    if imported:
        files['orket/adapters/validation.py'] = validator
    return files


@pytest.mark.parametrize('imported', [False, True])
@pytest.mark.parametrize('operation', ['importlib.import_module(name)', 'sys.modules.get(name)'])
def test_validated_external_names_have_explicit_observations(tmp_path: Path, imported: bool, operation: str) -> None:
    make_repository(tmp_path, _files('    name = external_name(value)\n    return ' + operation + '\n', imported=imported))
    process, report = run_command(tmp_path)
    assert process.returncode == 0 and report['verdict']['ok'], report
    row, = report['observed']['resolved_dynamic_routes']
    assert row['excluded_namespace'] == 'orket' and row['plain_string'] and row['absolute_name']
    assert row['kind'] == ('external_module_cache_read' if operation.startswith('sys.') else 'external_module_import')


@pytest.mark.parametrize('change', [
    'no_type', 'subclass_allowed', 'relative_allowed', 'root_allowed', 'child_allowed', 'and_guard',
    'changed_return', 'decorated', 'type_shadowed', 'str_shadowed', 'builtin_type_changed', 'builtin_escape',
])
def test_missing_or_untrustworthy_validator_guards_fail(tmp_path: Path, change: str) -> None:
    replacements = {
        'no_type': VALIDATOR.replace('    if type(name) is not str:\n        raise TypeError()\n', ''),
        'subclass_allowed': VALIDATOR.replace('type(name) is not str', 'not isinstance(name, str)'),
        'relative_allowed': VALIDATOR.replace("    if name.startswith('.'):\n        raise ValueError()\n", ''),
        'root_allowed': VALIDATOR.replace("name == 'orket' or ", ''),
        'child_allowed': VALIDATOR.replace(" or name.startswith('orket.')", ''),
        'and_guard': VALIDATOR.replace(" or name.startswith('orket.')", " and name.startswith('orket.')"),
        'changed_return': VALIDATOR.replace('    return name', "    return 'orket.application.target'"),
        'decorated': '@unknown\n' + VALIDATOR,
        'type_shadowed': 'type = unknown\n' + VALIDATOR,
        'str_shadowed': 'str = unknown\n' + VALIDATOR,
        'builtin_type_changed': 'import builtins\nbuiltins.type = unknown\n' + VALIDATOR,
        'builtin_escape': 'import builtins\ncallback(builtins)\n' + VALIDATOR,
    }
    make_repository(tmp_path, _files('    name = external_name(value)\n    return importlib.import_module(name)\n',
                                     validator=replacements[change]))
    process, report = run_command(tmp_path)
    assert process.returncode == 1 and not report['verdict']['ok'], report
    assert not report['observed']['resolved_dynamic_routes']


@pytest.mark.parametrize('body', [
    '    name = external_name(value)\n    name = value\n    return importlib.import_module(name)\n',
    '    if value:\n        name = external_name(value)\n    return importlib.import_module(name)\n',
    '    name = external_name(value)\n    for name in values:\n        importlib.import_module(name)\n',
    '    name = external_name(value)\n    return [importlib.import_module(name) for name in values]\n',
    '    name = external_name(value)\n    return lambda: importlib.import_module(name)\n',
    '    global name\n    name = external_name(value)\n    callback()\n    return importlib.import_module(name)\n',
    '    def change():\n        nonlocal name\n        name = value\n'
    '    name = external_name(value)\n    change()\n    return importlib.import_module(name)\n',
    '    name = external_name(value)\n    from somewhere import changed as name\n    return importlib.import_module(name)\n',
    '    name = external_name(value)\n    try:\n        callback()\n    except Error as name:\n'
    '        return importlib.import_module(name)\n',
])
def test_validation_does_not_cross_unproved_bindings_or_scopes(tmp_path: Path, body: str) -> None:
    make_repository(tmp_path, _files(body))
    process, report = run_command(tmp_path)
    assert process.returncode == 1 and not report['verdict']['ok'], report
    assert not report['observed']['resolved_dynamic_routes']


def test_loop_local_validation_can_dominate_each_lookup(tmp_path: Path) -> None:
    body = ('    for value in values:\n        name = external_name(value)\n'
            '        importlib.import_module(name)\n')
    make_repository(tmp_path, _files(body))
    process, report = run_command(tmp_path)
    assert process.returncode == 0 and report['verdict']['ok'], report
    assert len(report['observed']['resolved_dynamic_routes']) == 1


def test_validator_module_mutation_invalidates_the_binding(tmp_path: Path) -> None:
    files = _files('    name = external_name(value)\n    return importlib.import_module(name)\n', imported=True)
    files['orket/application/mutation.py'] = (
        'import orket.adapters.validation as validation\nvalidation.external_name = unknown\n'
    )
    make_repository(tmp_path, files)
    process, report = run_command(tmp_path)
    assert process.returncode == 1 and not report['verdict']['ok'], report
    assert not report['observed']['resolved_dynamic_routes']


def test_export_reports_the_actual_proven_route_separately(tmp_path: Path) -> None:
    make_repository(tmp_path, _files('    name = external_name(value)\n    return importlib.import_module(name)\n'))
    process, report = run_command(tmp_path, exporter=True)
    assert process.returncode == 0 and report['verdict']['ok']
    markdown = (tmp_path / 'export.md').read_text(encoding='utf-8')
    assert 'not analysis-error waivers' in markdown
    assert 'external_module_import' in markdown and 'Plain absolute name outside `orket`' in markdown
