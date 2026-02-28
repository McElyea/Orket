from __future__ import annotations

import json

from orket.extensions.manager import ExtensionManager


def test_list_extensions_from_catalog(tmp_path):
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
    extensions = manager.list_extensions()

    assert len(extensions) == 1
    assert extensions[0].extension_id == "mystery.extension"
    assert extensions[0].workloads[0].workload_id == "mystery_v1"


def test_resolve_workload_returns_extension_and_workload(tmp_path):
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
    resolved = manager.resolve_workload("mystery_v1")

    assert resolved is not None
    extension, workload = resolved
    assert extension.extension_id == "mystery.extension"
    assert workload.workload_id == "mystery_v1"
