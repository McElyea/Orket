from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from orket.extensions.manager import ExtensionManager
from orket.interfaces.cli import _print_extensions_list, _run_extension_workload


def test_print_extensions_list_shows_installed_extensions(tmp_path, capsys):
    catalog = tmp_path / "extensions_catalog.json"
    catalog.write_text(
        json.dumps(
            {
                "extensions": [
                    {
                        "extension_id": "mystery.extension",
                        "extension_version": "1.0.0",
                        "source": "git+https://example/repo.git",
                        "workloads": [
                            {"workload_id": "mystery_v1", "workload_version": "1.0.0"},
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    manager = ExtensionManager(catalog_path=catalog)

    _print_extensions_list(manager)
    out = capsys.readouterr().out

    assert "Installed extensions:" in out
    assert "mystery.extension (1.0.0)" in out
    assert "workload: mystery_v1 (1.0.0)" in out


def test_run_extension_workload_requires_registered_workload(tmp_path):
    manager = ExtensionManager(catalog_path=tmp_path / "extensions_catalog.json")
    args = SimpleNamespace(subcommand="missing_workload", seed=123)

    with pytest.raises(ValueError):
        _run_extension_workload(args, manager)


def test_run_extension_workload_resolves_and_reports_unimplemented(tmp_path):
    catalog = tmp_path / "extensions_catalog.json"
    catalog.write_text(
        json.dumps(
            {
                "extensions": [
                    {
                        "extension_id": "mystery.extension",
                        "extension_version": "1.0.0",
                        "source": "git+https://example/repo.git",
                        "workloads": [
                            {"workload_id": "mystery_v1", "workload_version": "1.0.0"},
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    manager = ExtensionManager(catalog_path=catalog)
    args = SimpleNamespace(subcommand="mystery_v1", seed=123)

    with pytest.raises(RuntimeError) as exc:
        _run_extension_workload(args, manager)
    assert "Extension workload runner not implemented yet" in str(exc.value)
