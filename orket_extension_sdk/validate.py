from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Any

from .capabilities import load_capability_vocab, validate_capabilities
from .import_scan import scan_extension_imports
from .manifest import ExtensionManifest, load_manifest

ERROR_SDK_MANIFEST_NOT_FOUND = "E_SDK_MANIFEST_NOT_FOUND"
ERROR_SDK_ENTRYPOINT_INVALID = "E_SDK_ENTRYPOINT_INVALID"
ERROR_SDK_ENTRYPOINT_MISSING = "E_SDK_ENTRYPOINT_MISSING"


def _resolve_manifest_path(target: Path) -> Path | None:
    if target.is_file():
        return target
    for filename in ("extension.yaml", "extension.yml", "extension.json"):
        candidate = target / filename
        if candidate.is_file():
            return candidate
    return None


def _resolve_import_scan_target(extension_root: Path) -> Path:
    source_root = extension_root / "src"
    if source_root.is_dir():
        return source_root
    return extension_root


def _parse_entrypoint(value: str) -> tuple[str, str]:
    module_name, sep, attr_name = str(value or "").strip().partition(":")
    if sep != ":" or not module_name.strip() or not attr_name.strip():
        raise ValueError(ERROR_SDK_ENTRYPOINT_INVALID)
    return module_name.strip(), attr_name.strip()


def _resolve_module_source(extension_root: Path, module_name: str) -> Path | None:
    for search_root in (extension_root, extension_root / "src"):
        module_path = search_root / Path(*module_name.split("."))
        file_path = module_path.with_suffix(".py")
        package_init = module_path / "__init__.py"
        if file_path.is_file():
            return file_path
        if package_init.is_file():
            return package_init
    return None


def _symbol_exists_in_module(module_source: Path, symbol_name: str) -> tuple[bool, str | None]:
    try:
        source = module_source.read_text(encoding="utf-8-sig")
        tree = ast.parse(source, filename=str(module_source))
    except (OSError, SyntaxError, UnicodeDecodeError) as exc:
        return False, str(exc)

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == symbol_name:
            return True, None
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == symbol_name:
                    return True, None
        if isinstance(node, ast.AnnAssign):
            target = node.target
            if isinstance(target, ast.Name) and target.id == symbol_name:
                return True, None

    return False, None


def _manifest_error_payload(target: Path, manifest_path: Path, message: str) -> dict[str, Any]:
    code = str(message).split(":", 1)[0] if str(message).startswith("E_SDK_") else "E_SDK_MANIFEST_PARSE"
    return {
        "ok": False,
        "target": str(target),
        "manifest_path": str(manifest_path),
        "error_count": 1,
        "warning_count": 0,
        "errors": [
            {
                "code": code,
                "location": str(manifest_path.name),
                "message": str(message),
            }
        ],
        "warnings": [],
        "exit_code": 2,
    }


def validate_extension(
    target: Path,
    *,
    strict: bool = False,
    include_import_scan: bool = False,
) -> dict[str, Any]:
    manifest_path = _resolve_manifest_path(target)
    if manifest_path is None:
        return {
            "ok": False,
            "target": str(target),
            "error_count": 1,
            "warning_count": 0,
            "errors": [
                {
                    "code": ERROR_SDK_MANIFEST_NOT_FOUND,
                    "location": "manifest",
                    "message": "Manifest not found. Expected one of: extension.yaml, extension.yml, extension.json",
                }
            ],
            "warnings": [],
            "exit_code": 2,
        }

    try:
        manifest: ExtensionManifest = load_manifest(manifest_path)
    except ValueError as exc:
        return _manifest_error_payload(target, manifest_path, str(exc))

    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    extension_root = manifest_path.parent.resolve()

    for workload in manifest.workloads:
        location = f"workloads.{workload.workload_id}"
        try:
            module_name, attr_name = _parse_entrypoint(workload.entrypoint)
        except ValueError:
            errors.append(
                {
                    "code": ERROR_SDK_ENTRYPOINT_INVALID,
                    "location": f"{location}.entrypoint",
                    "message": f"Invalid entrypoint format: {workload.entrypoint}",
                }
            )
            continue

        module_source = _resolve_module_source(extension_root, module_name)
        if module_source is None:
            errors.append(
                {
                    "code": ERROR_SDK_ENTRYPOINT_MISSING,
                    "location": f"{location}.entrypoint",
                    "message": f"Unable to resolve module source '{module_name}' under extension root.",
                }
            )
        else:
            symbol_exists, parse_error = _symbol_exists_in_module(module_source, attr_name)
            if parse_error:
                errors.append(
                    {
                        "code": ERROR_SDK_ENTRYPOINT_MISSING,
                        "location": f"{location}.entrypoint",
                        "message": f"Unable to parse module '{module_name}': {parse_error}",
                    }
                )
            elif not symbol_exists:
                errors.append(
                    {
                        "code": ERROR_SDK_ENTRYPOINT_MISSING,
                        "location": f"{location}.entrypoint",
                        "message": f"Entrypoint attr '{attr_name}' not found in module '{module_name}'",
                    }
                )

        cap_errors, cap_warnings = validate_capabilities(
            list(workload.required_capabilities),
            strict=strict,
            vocab=load_capability_vocab(),
        )
        for code in cap_errors:
            errors.append(
                {
                    "code": code.split(":", 1)[0],
                    "location": f"{location}.required_capabilities",
                    "message": code,
                }
            )
        for code in cap_warnings:
            warnings.append(
                {
                    "code": code.split(":", 1)[0],
                    "location": f"{location}.required_capabilities",
                    "message": code,
                }
            )

    import_scan_result: dict[str, Any] | None = None
    if include_import_scan:
        scan_target = _resolve_import_scan_target(extension_root)
        import_scan_result = scan_extension_imports(scan_target)
        for item in import_scan_result["errors"]:
            errors.append(
                {
                    "code": str(item.get("code") or "E_SDK_IMPORT_SCAN"),
                    "location": str(item.get("location") or "import_scan"),
                    "message": str(item.get("message") or "import-scan error"),
                }
            )

    errors.sort(key=lambda item: (item["code"], item["location"], item["message"]))
    warnings.sort(key=lambda item: (item["code"], item["location"], item["message"]))
    ok = len(errors) == 0
    result: dict[str, Any] = {
        "ok": ok,
        "target": str(target),
        "manifest_path": str(manifest_path),
        "manifest_version": manifest.manifest_version,
        "extension_id": manifest.extension_id,
        "workload_count": len(manifest.workloads),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "exit_code": 0 if ok else 2,
    }
    if import_scan_result is not None:
        result["import_scan"] = {
            "scanned_file_count": int(import_scan_result.get("scanned_file_count") or 0),
            "error_count": int(import_scan_result.get("error_count") or 0),
        }
    return result


def _render_human(result: dict[str, Any]) -> str:
    if bool(result.get("ok")):
        return (
            f"OK: {result.get('extension_id', '')} "
            f"(workloads={result.get('workload_count', 0)}, warnings={result.get('warning_count', 0)})"
        )
    lines = [f"FAIL ({result.get('error_count', 0)} error(s))"]
    for item in list(result.get("errors") or []):
        lines.append(f"[{item.get('code')}] {item.get('location')}: {item.get('message')}")
    return "\n".join(lines)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m orket_extension_sdk.validate",
        description="Validate SDK extension manifests and declared workload entrypoints.",
    )
    parser.add_argument("target", nargs="?", default=".", help="Extension directory or manifest path.")
    parser.add_argument("--strict", action="store_true", help="Treat unknown capabilities as errors.")
    parser.add_argument(
        "--with-import-scan",
        action="store_true",
        help="Also run static import scanning against extension Python files.",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = validate_extension(
        Path(args.target),
        strict=bool(args.strict),
        include_import_scan=bool(args.with_import_scan),
    )
    if bool(args.json):
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(_render_human(result))
    for item in result.get("warnings", []):
        print(
            f"[{item.get('code')}] {item.get('location')}: {item.get('message')}",
            file=sys.stderr,
        )
    return int(result.get("exit_code", 2))


if __name__ == "__main__":
    raise SystemExit(main())
