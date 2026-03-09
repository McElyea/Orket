from __future__ import annotations

from pathlib import Path

from orket_extension_sdk.validate import validate_extension


def _write_extension(
    root: Path,
    *,
    module_source: str,
    required_capabilities: list[str] | None = None,
) -> None:
    required = list(required_capabilities or [])
    (root / "demo_workload.py").write_text(module_source, encoding="utf-8")
    required_lines = ["    required_capabilities: []"]
    if required:
        required_lines = ["    required_capabilities:", *[f"      - {cap}" for cap in required]]
    (root / "extension.yaml").write_text(
        "\n".join(
            [
                "manifest_version: v0",
                "extension_id: demo",
                "extension_version: 1.0.0",
                "workloads:",
                "  - workload_id: w1",
                "    entrypoint: demo_workload:run",
                *required_lines,
            ]
        ),
        encoding="utf-8",
    )


def test_validate_extension_unknown_capability_warns_by_default(tmp_path: Path) -> None:
    """Layer: contract. Verifies capability vocab enforcement stays warning-only outside strict mode."""
    _write_extension(
        tmp_path,
        module_source="def run(ctx, payload):\n    return payload\n",
        required_capabilities=["future.capability"],
    )
    result = validate_extension(tmp_path, strict=False)

    assert result["ok"] is True
    assert result["warning_count"] == 1
    assert result["error_count"] == 0
    assert result["warnings"][0]["code"] == "E_SDK_CAPABILITY_UNKNOWN"


def test_validate_extension_with_import_scan_blocks_internal_imports(tmp_path: Path) -> None:
    """Layer: integration. Verifies validate flow can fail closed on disallowed internal imports."""
    _write_extension(
        tmp_path,
        module_source="\n".join(
            [
                "import orket.adapters",
                "",
                "def run(ctx, payload):",
                "    return payload",
            ]
        )
        + "\n",
    )
    result = validate_extension(tmp_path, include_import_scan=True)

    assert result["ok"] is False
    assert any(item["code"] == "E_SDK_IMPORT_FORBIDDEN" for item in result["errors"])
    assert result["import_scan"]["error_count"] == 1


def test_validate_extension_resolves_src_layout_entrypoints(tmp_path: Path) -> None:
    """Layer: contract. Verifies entrypoint module resolution supports `src/` package layout."""
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

    result = validate_extension(tmp_path)
    assert result["ok"] is True
    assert result["error_count"] == 0
