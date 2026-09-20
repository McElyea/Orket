"""Contract checks for the actual extension-name boundary before source lookup."""
from __future__ import annotations

from pathlib import Path

import pytest

from orket.adapters.execution.extension_modules import extension_module_sources

pytestmark = pytest.mark.contract


class ForgedName(str):
    def startswith(self, *_args, **_kwargs):
        raise AssertionError('A string subclass reached the namespace predicate')


@pytest.mark.parametrize('name', [None, 1, ['selected'], ForgedName('selected'), ForgedName('orket.core')])
def test_extension_names_require_plain_strings_before_lookup(tmp_path: Path, name: object) -> None:
    with pytest.raises(TypeError, match='E_EXT_MODULE_NAME_INVALID: expected a plain string'):
        extension_module_sources(tmp_path / 'absent', name)
    assert not (tmp_path / 'absent').exists()


@pytest.mark.parametrize('name,code', [
    ('orket', 'RESERVED'), ('orket.core', 'RESERVED'),
    ('orket_extension_sdk', 'RESERVED'), ('orket_extension_sdk.agent', 'RESERVED'),
    ('.selected', 'INVALID'), ('..selected', 'INVALID'), ('', 'INVALID'), ('selected-name', 'INVALID'),
])
def test_reserved_relative_and_invalid_names_fail_before_source_lookup(tmp_path: Path, name: str, code: str) -> None:
    with pytest.raises(ValueError, match='E_EXT_MODULE_NAME_' + code):
        extension_module_sources(tmp_path / 'absent', name)
    assert not (tmp_path / 'absent').exists()


def test_plain_external_name_retains_deterministic_source_resolution(tmp_path: Path) -> None:
    source = tmp_path / 'selected.py'
    source.write_text('VALUE = 1\n', encoding='utf-8')
    first = extension_module_sources(tmp_path, 'selected')
    assert extension_module_sources(tmp_path, 'selected') == first
    assert len(first) == 1 and first[0].name == 'selected' and first[0].origin == source.resolve()
