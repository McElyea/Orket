from __future__ import annotations

import json
from pathlib import Path

from orket.interfaces.orket_bundle_cli import main


def _write_extension(root: Path, *, workload_source: str) -> None:
    (root / "demo_workload.py").write_text(workload_source, encoding="utf-8")
    (root / "extension.yaml").write_text(
        "\n".join(
            [
                "manifest_version: v0",
                "extension_id: demo",
                "extension_version: 1.0.0",
                "workloads:",
                "  - workload_id: w1",
                "    entrypoint: demo_workload:run",
                "    required_capabilities: []",
            ]
        ),
        encoding="utf-8",
    )


def test_ext_validate_passes_for_minimal_extension(tmp_path: Path, capsys) -> None:
    """Layer: integration. Verifies external-extension validation succeeds for a minimal valid layout."""
    _write_extension(tmp_path, workload_source="def run(ctx, payload):\n    return payload\n")
    code = main(["ext", "validate", str(tmp_path), "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["ok"] is True
    assert payload["import_scan"]["error_count"] == 0


def test_ext_validate_blocks_internal_orket_imports(tmp_path: Path, capsys) -> None:
    """Layer: integration. Verifies external-extension validation enforces import-isolation policy."""
    _write_extension(
        tmp_path,
        workload_source="\n".join(
            [
                "import orket.runtime.provider_runtime_target",
                "",
                "def run(ctx, payload):",
                "    return payload",
            ]
        )
        + "\n",
    )
    code = main(["ext", "validate", str(tmp_path), "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 2
    assert payload["ok"] is False
    assert any(item["code"] == "E_SDK_IMPORT_FORBIDDEN" for item in payload["errors"])


def test_ext_validate_rejects_unsupported_manifest_version(tmp_path: Path, capsys) -> None:
    _write_extension(tmp_path, workload_source="def run(ctx, payload):\n    return payload\n")
    (tmp_path / "extension.yaml").write_text(
        "\n".join(
            [
                "manifest_version: v1",
                "extension_id: demo",
                "extension_version: 1.0.0",
                "workloads:",
                "  - workload_id: w1",
                "    entrypoint: demo_workload:run",
                "    required_capabilities: []",
            ]
        ),
        encoding="utf-8",
    )

    code = main(["ext", "validate", str(tmp_path), "--strict", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 2
    assert payload["ok"] is False
    assert payload["error_count"] == 1
    assert payload["errors"][0]["code"] == "E_SDK_MANIFEST_VERSION_UNSUPPORTED"


def test_ext_validate_ignores_local_virtualenv_trees(tmp_path: Path, capsys) -> None:
    """Layer: integration. Verifies host validation import scanning stays scoped to extension source, not local virtualenv trees."""
    src_pkg = tmp_path / "src" / "demo_pkg"
    src_pkg.mkdir(parents=True, exist_ok=True)
    (src_pkg / "__init__.py").write_text("", encoding="utf-8")
    (src_pkg / "workload.py").write_text("def run(ctx, payload):\n    return payload\n", encoding="utf-8")
    (tmp_path / "extension.yaml").write_text(
        "\n".join(
            [
                "manifest_version: v0",
                "extension_id: demo",
                "extension_version: 1.0.0",
                "workloads:",
                "  - workload_id: w1",
                "    entrypoint: demo_pkg.workload:run",
                "    required_capabilities: []",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    venv_site = tmp_path / ".venv" / "Lib" / "site-packages"
    venv_site.mkdir(parents=True, exist_ok=True)
    (venv_site / "bad_dependency.py").write_text(
        "import orket.runtime.provider_runtime_target\n",
        encoding="utf-8",
    )

    code = main(["ext", "validate", str(tmp_path), "--strict", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["ok"] is True
    assert payload["import_scan"]["error_count"] == 0
    assert payload["import_scan"]["scanned_file_count"] == 2
