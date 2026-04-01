from __future__ import annotations

from pathlib import Path

from orket_extension_sdk.import_scan import scan_extension_imports


def test_import_scan_reports_internal_orket_imports(tmp_path: Path) -> None:
    """Layer: contract. Verifies static import scan blocks `orket.*` internal imports."""
    source_dir = tmp_path / "src"
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "workload.py").write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "import orket.runtime.provider_runtime_target",
                "",
                "def run(ctx, payload):",
                "    return payload",
            ]
        ),
        encoding="utf-8",
    )

    result = scan_extension_imports(source_dir)
    assert result["ok"] is False
    assert result["error_count"] == 1
    assert result["errors"][0]["code"] == "E_SDK_IMPORT_FORBIDDEN"


def test_import_scan_ignores_local_virtualenv_trees(tmp_path: Path) -> None:
    """Layer: contract. Verifies static import scan ignores local virtualenv trees under the extension root."""
    source_dir = tmp_path / "src"
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "workload.py").write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "",
                "def run(ctx, payload):",
                "    return payload",
            ]
        ),
        encoding="utf-8",
    )

    venv_site = tmp_path / ".venv" / "Lib" / "site-packages"
    venv_site.mkdir(parents=True, exist_ok=True)
    (venv_site / "bad_dependency.py").write_text(
        "import orket.runtime.provider_runtime_target\n",
        encoding="utf-8",
    )

    result = scan_extension_imports(tmp_path)

    assert result["ok"] is True
    assert result["scanned_file_count"] == 1
    assert result["error_count"] == 0
