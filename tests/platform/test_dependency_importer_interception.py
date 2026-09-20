"""Contract proof for statically bounded standard-importer interception."""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers.dependency_repository import make_repository, run_command

pytestmark = pytest.mark.contract

FACTORY = (
    'def guard(original):\n'
    '    def wrapped(name, package=None):\n'
    '        return original(name, package)\n'
    '    return wrapped\n'
)
INSTALL = 'importlib.import_module = guard(importlib.import_module)\n'


def _files(*, factory: str = FACTORY, install: str = INSTALL, imported: bool = False) -> dict[str, str]:
    source = 'import importlib\n'
    if imported:
        source += 'from orket.adapters.hooks import guard\n'
    else:
        source += factory
    result = {'orket/adapters/source.py': source + install, 'orket/application/target.py': ''}
    if imported:
        result['orket/adapters/hooks.py'] = factory
    return result


@pytest.mark.parametrize('imported', [False, True])
def test_native_argument_preserving_interception_is_observed(tmp_path: Path, imported: bool) -> None:
    make_repository(tmp_path, _files(imported=imported))
    process, report = run_command(tmp_path)
    assert process.returncode == 0, report
    assert report['verdict']['ok'] and not report['observed']['analysis_errors']
    routes = report['observed']['resolved_dynamic_routes']
    assert len(routes) == 1
    assert routes[0]['kind'] == 'importer_interception'
    assert routes[0]['target'] == 'importlib.import_module'
    assert routes[0]['forwarded_arguments'] == 2
    assert routes[0]['factory'] == 'orket.adapters.' + ('hooks' if imported else 'source') + '.guard'


def test_native_builtin_interception_with_validation_prefix(tmp_path: Path) -> None:
    source = (
        'import builtins\n'
        'def guard(hook, original):\n'
        '    def wrapped(name, globals=None, locals=None, fromlist=(), level=0):\n'
        '        if level == 0:\n'
        '            hook.validate_import(name)\n'
        '        return original(name, globals, locals, fromlist, level)\n'
        '    return wrapped\n'
        'builtins.__import__ = guard(hook, builtins.__import__)\n'
    )
    make_repository(tmp_path, {'orket/adapters/source.py': source})
    process, report = run_command(tmp_path)
    assert process.returncode == 0, report
    assert report['observed']['resolved_dynamic_routes'][0]['target'] == 'builtins.__import__'


def test_repeated_imports_of_the_same_namespace_preserve_identity(tmp_path: Path) -> None:
    files = _files()
    files['orket/adapters/source.py'] = 'import importlib.abc\n' + files['orket/adapters/source.py']
    make_repository(tmp_path, files)
    process, report = run_command(tmp_path)
    assert process.returncode == 0, report
    assert len(report['observed']['resolved_dynamic_routes']) == 1


@pytest.mark.parametrize('change', [
    'redirected', 'reordered', 'dropped', 'rebound_argument', 'decorated_outer', 'decorated_inner',
    'duplicate_factory', 'rebound_factory', 'parameter_shadow', 'factory_escape', 'factory_code_mutation',
    'starred_call', 'different_importer', 'noninstallation', 'extra_capture', 'namespace_rebound',
])
def test_native_interception_uncertainty_stays_a_failure(tmp_path: Path, change: str) -> None:
    factories = {
        'redirected': FACTORY.replace('original(name, package)', "original('orket.application.target', package)"),
        'reordered': FACTORY.replace('original(name, package)', 'original(package, name)'),
        'dropped': FACTORY.replace('original(name, package)', 'original(name)'),
        'rebound_argument': FACTORY.replace('        return', "        name = 'orket.application.target'\n        return"),
        'decorated_outer': '@unknown\n' + FACTORY,
        'decorated_inner': FACTORY.replace('    def wrapped', '    @unknown\n    def wrapped'),
        'duplicate_factory': FACTORY + FACTORY,
        'rebound_factory': FACTORY + 'guard = unknown\n',
        'factory_escape': FACTORY + 'callback(guard)\n',
        'factory_code_mutation': FACTORY + 'guard.__code__ = unknown\n',
    }
    installs = {
        'parameter_shadow': 'def install(guard):\n    ' + INSTALL,
        'starred_call': 'importlib.import_module = guard(*unknown, importlib.import_module)\n',
        'different_importer': 'import builtins\nimportlib.import_module = guard(builtins.__import__)\n',
        'noninstallation': 'callback(guard(importlib.import_module))\n',
        'extra_capture': 'importlib.import_module = guard(importlib.import_module, importlib.import_module)\n',
        'namespace_rebound': 'importlib = unknown\n' + INSTALL,
    }
    make_repository(tmp_path, _files(factory=factories.get(change, FACTORY), install=installs.get(change, INSTALL)))
    process, report = run_command(tmp_path)
    assert process.returncode == 1 and not report['verdict']['ok'], report
    assert not report['observed']['resolved_dynamic_routes']
    assert 'importer_escape' in {row['code'] for row in report['verdict']['analysis_errors']}


@pytest.mark.parametrize('mutation', [
    'hooks.guard = unknown', 'callback(hooks)', 'namespace = hooks.__dict__',
    "setattr(hooks, 'guard', unknown)", 'alias = hooks',
])
def test_imported_factory_namespace_cannot_mutate_or_escape(tmp_path: Path, mutation: str) -> None:
    files = _files(imported=True)
    files['orket/application/mutation.py'] = 'import orket.adapters.hooks as hooks\n' + mutation + '\n'
    make_repository(tmp_path, files)
    process, report = run_command(tmp_path)
    assert process.returncode == 1 and not report['verdict']['ok'], report
    assert not report['observed']['resolved_dynamic_routes']
    assert 'importer_escape' in {row['code'] for row in report['verdict']['analysis_errors']}


@pytest.mark.parametrize('target,code', [
    ("'orket.application.target'", None), ('unknown', 'unresolved_dynamic_import'),
])
def test_interception_does_not_hide_other_import_routes(tmp_path: Path, target: str, code: str | None) -> None:
    files = _files(imported=True, install=INSTALL + f'importlib.import_module({target})\n')
    make_repository(tmp_path, files)
    process, report = run_command(tmp_path)
    assert process.returncode == 1 and not report['verdict']['ok'], report
    assert len(report['observed']['resolved_dynamic_routes']) == 1
    if code:
        assert code in {row['code'] for row in report['verdict']['analysis_errors']}
    else:
        assert {row['target'] for row in report['verdict']['violations']} == {'orket.application.target'}
