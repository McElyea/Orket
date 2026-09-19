"""Real loader admission through isolated Python processes and selected sources."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import orket

pytestmark = pytest.mark.integration

_PROBE = '''
import json, sys
from pathlib import Path
from orket.extensions.models import ExtensionRecord, _ExtensionManifestEntry
from orket.extensions.workload_loader import WorkloadLoader

class Registry:
    def __init__(self): self.items = {}
    def register_workload(self, item): self.items[item.workload_id] = item
    def workloads(self): return self.items

loader = WorkloadLoader(Registry)
observed = []
before = list(sys.path)
for row in json.loads(sys.argv[2]):
    root, module = row
    entry = _ExtensionManifestEntry('fixture', '1', entrypoint=module + ':Work')
    record = ExtensionRecord(root, '1', 'fixture', '1', root, module, 'register', (entry,))
    try:
        if sys.argv[1] == 'legacy':
            item = loader.load_legacy_workload(record, 'fixture')
        else:
            item = loader.load_sdk_workload(record, entry)
    except (ImportError, ValueError, FileNotFoundError) as exc:
        observed.append({'error': str(exc), 'type': type(exc).__name__})
    else:
        observed.append({'marker': item.marker})
print(json.dumps({'observed': observed, 'path_retained': before == sys.path}))
'''


def _source(root: Path, module: str, marker: str) -> None:
    target = root.joinpath(*module.split('.')).with_suffix('.py')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        'class Work:\n    workload_id = "fixture"\n    workload_version = "1"\n'
        f'    marker = "{marker}"\n    def run(self, ctx, payload): return self.marker\n'
        'def register(registry): registry.register_workload(Work())\n', encoding='utf-8',
    )


def _probe(tmp_path: Path, kind: str, selections: list[tuple[Path, str]]) -> dict:
    script = tmp_path / 'probe.py'
    script.write_text(_PROBE, encoding='utf-8')
    env = dict(os.environ, ORKET_DISABLE_SANDBOX='1', PYTHONPATH=str(Path(orket.__file__).parent.parent))
    completed = subprocess.run(
        [sys.executable, str(script), kind, json.dumps([(str(root), name) for root, name in selections])],
        cwd=tmp_path, env=env, text=True, capture_output=True, timeout=20,
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result['path_retained']
    return result


@pytest.mark.parametrize('kind', ['legacy', 'sdk'])
def test_conflicting_root_never_adopts_cached_workload(tmp_path: Path, kind: str) -> None:
    """Layer: integration. A second selected root cannot report the first root's object."""
    first, second = tmp_path / 'first', tmp_path / 'second'
    _source(first, 'selected', 'first')
    _source(second, 'selected', 'second')
    rows = _probe(tmp_path, kind, [(first, 'selected'), (second, 'selected')])['observed']
    assert rows[0] == {'marker': 'first'}
    assert 'E_EXT_MODULE_ORIGIN_MISMATCH' in rows[1].get('error', ''), rows


@pytest.mark.parametrize('kind', ['legacy', 'sdk'])
def test_repeated_root_and_distinct_modules_keep_working(tmp_path: Path, kind: str) -> None:
    """Layer: integration. Valid repeated loads and independent module names preserve their results."""
    first, second = tmp_path / 'first', tmp_path / 'second'
    _source(first, 'selected_one', 'first')
    _source(second, 'selected_two', 'second')
    rows = _probe(tmp_path, kind, [(first, 'selected_one'), (first, 'selected_one'),
                                  (second, 'selected_two')])['observed']
    assert rows == [{'marker': 'first'}, {'marker': 'first'}, {'marker': 'second'}]


@pytest.mark.parametrize('kind', ['legacy', 'sdk'])
def test_package_parent_conflict_refuses_before_second_initializer(tmp_path: Path, kind: str) -> None:
    """Layer: integration. Parent identity is checked even when the requested leaf name differs."""
    first, second = tmp_path / 'first', tmp_path / 'second'
    _source(first, 'selected_pkg.one', 'first')
    _source(first, 'selected_pkg.two', 'wrong')
    _source(second, 'selected_pkg.two', 'second')
    for root in (first, second):
        (root / 'selected_pkg/__init__.py').write_text('', encoding='utf-8')
    rows = _probe(tmp_path, kind, [(first, 'selected_pkg.one'), (second, 'selected_pkg.two')])['observed']
    assert rows[0] == {'marker': 'first'}
    assert 'E_EXT_MODULE_ORIGIN_MISMATCH' in rows[1].get('error', ''), rows


@pytest.mark.parametrize('kind', ['legacy', 'sdk'])
def test_actual_package_initializer_is_validated_before_execution(tmp_path: Path, kind: str) -> None:
    """Layer: integration. A harmless same-named file cannot hide a forbidden package import."""
    root = tmp_path / 'extension'
    _source(root, 'selected', 'file')
    _source(root, 'selected.__init__', 'package')
    initializer = root / 'selected/__init__.py'
    initializer.write_text('import orket.application\n' + initializer.read_text(encoding='utf-8'), encoding='utf-8')
    rows = _probe(tmp_path, kind, [(root, 'selected')])['observed']
    assert 'Extension import blocked by isolation policy' in rows[0].get('error', ''), rows


@pytest.mark.parametrize('kind', ['legacy', 'sdk'])
def test_all_package_initializers_are_validated(tmp_path: Path, kind: str) -> None:
    """Layer: integration. Selecting a clean leaf cannot bypass its parent's import policy."""
    root = tmp_path / 'extension'
    _source(root, 'selected_pkg.leaf', 'leaf')
    (root / 'selected_pkg/__init__.py').write_text('import orket.application\n', encoding='utf-8')
    rows = _probe(tmp_path, kind, [(root, 'selected_pkg.leaf')])['observed']
    assert 'Extension import blocked by isolation policy' in rows[0].get('error', ''), rows


@pytest.mark.parametrize('kind', ['legacy', 'sdk'])
def test_namespace_parent_and_construction_import_keep_selected_path(tmp_path: Path, kind: str) -> None:
    """Layer: integration. Namespace parents and imports during construction retain selection."""
    root = tmp_path / 'extension'
    _source(root, 'selected_pkg.leaf', 'leaf')
    (root / 'selected_helper.py').write_text('MARKER = "helper"\n', encoding='utf-8')
    leaf = root / 'selected_pkg/leaf.py'
    leaf.write_text(leaf.read_text(encoding='utf-8').replace(
        '    def run(', '    def __init__(self):\n        from selected_helper import MARKER\n'
        '        self.marker = MARKER\n    def run('), encoding='utf-8')
    assert _probe(tmp_path, kind, [(root, 'selected_pkg.leaf')])['observed'] == [{'marker': 'helper'}]


@pytest.mark.parametrize('kind', ['legacy', 'sdk'])
def test_package_search_path_redirection_refuses_before_leaf_execution(tmp_path: Path, kind: str) -> None:
    """Layer: integration. The observed package path must agree with the selected local source."""
    root, outside = tmp_path / 'extension', tmp_path / 'outside'
    _source(root, 'selected_pkg.leaf', 'inside')
    _source(outside, 'leaf', 'outside')
    sentinel = outside / 'executed'
    leaf = outside / 'leaf.py'
    leaf.write_text(f'open({str(sentinel)!r}, "w").close()\n' + leaf.read_text(encoding='utf-8'), encoding='utf-8')
    (root / 'selected_pkg/__init__.py').write_text(f'__path__ = [{str(outside)!r}]\n', encoding='utf-8')
    rows = _probe(tmp_path, kind, [(root, 'selected_pkg.leaf')])['observed']
    assert 'E_EXT_MODULE_ORIGIN_MISMATCH' in rows[0].get('error', ''), rows
    assert not sentinel.exists()
