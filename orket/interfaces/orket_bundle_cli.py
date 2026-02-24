from __future__ import annotations

import argparse
import json
from importlib import metadata
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Tuple
import zipfile
import tomllib

from pydantic import ValidationError

from orket.core.domain.orket_manifest import (
    OrketManifest,
    is_engine_compatible,
    resolve_model_selection,
)
from orket.interfaces.api_generation import run_api_add_transaction
from orket.interfaces.refactor_transaction import run_refactor_transaction
from orket.interfaces.scaffold_init import run_scaffold_init


ERROR_MANIFEST_NOT_FOUND = "E_MANIFEST_NOT_FOUND"
ERROR_MANIFEST_PARSE = "E_MANIFEST_PARSE"
ERROR_MANIFEST_SCHEMA = "E_MANIFEST_SCHEMA"
ERROR_STATE_MACHINE_MISSING = "E_STATE_MACHINE_MISSING"
ERROR_AGENT_FILE_MISSING = "E_AGENT_FILE_MISSING"
ERROR_PROMPT_FILE_MISSING = "E_PROMPT_FILE_MISSING"
ERROR_GUARD_FILE_MISSING = "E_GUARD_FILE_MISSING"
ERROR_ENGINE_INCOMPATIBLE = "E_ENGINE_INCOMPATIBLE"
ERROR_PACK_SOURCE_NOT_DIRECTORY = "E_PACK_SOURCE_NOT_DIRECTORY"
ERROR_PACK_VALIDATE_FAILED = "E_PACK_VALIDATE_FAILED"
ERROR_PACK_UNSAFE_ARCHIVE_PATH = "E_PACK_UNSAFE_ARCHIVE_PATH"
ERROR_INSPECT_TARGET_NOT_FOUND = "E_INSPECT_TARGET_NOT_FOUND"
ERROR_INSPECT_MANIFEST_NOT_FOUND = "E_INSPECT_MANIFEST_NOT_FOUND"


def _resolve_manifest_path(target: Path) -> Tuple[Path | None, Path]:
    if target.is_file():
        return target, target.parent

    if not target.exists():
        return None, target

    for filename in ("orket.yaml", "orket.yml", "orket.json"):
        candidate = target / filename
        if candidate.is_file():
            return candidate, target
    return None, target


def _current_engine_version() -> str:
    try:
        return metadata.version("orket")
    except metadata.PackageNotFoundError:
        pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
        try:
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            version = str((data.get("project") or {}).get("version") or "").strip()
            return version or "0.0.0"
        except (OSError, tomllib.TOMLDecodeError, AttributeError):
            return "0.0.0"


def _parse_manifest_content(*, suffix: str, text: str) -> Dict[str, Any]:
    if suffix == ".json":
        raw = json.loads(text)
    elif suffix in {".yaml", ".yml"}:
        try:
            import yaml
        except ModuleNotFoundError as exc:
            raise ValueError("YAML parsing support is unavailable (missing PyYAML).") from exc
        raw = yaml.safe_load(text)
    else:
        raise ValueError(f"Unsupported manifest extension: {suffix}")
    if not isinstance(raw, dict):
        raise ValueError("Manifest payload must be an object.")
    return raw


def _load_manifest_payload(path: Path) -> Dict[str, Any]:
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8")
    return _parse_manifest_content(suffix=suffix, text=text)


def _schema_validation_errors(exc: ValidationError) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for item in exc.errors():
        loc = ".".join(str(part) for part in item.get("loc", ()))
        rows.append(
            {
                "code": ERROR_MANIFEST_SCHEMA,
                "location": loc,
                "message": str(item.get("msg") or "schema violation"),
            }
        )
    rows.sort(key=lambda row: (row["location"], row["message"]))
    return rows


def _bundle_reference_errors(bundle_root: Path, manifest: OrketManifest) -> List[Dict[str, str]]:
    errors: List[Dict[str, str]] = []

    state_machine_path = bundle_root / manifest.stateMachine.file
    if not state_machine_path.is_file():
        errors.append(
            {
                "code": ERROR_STATE_MACHINE_MISSING,
                "location": "stateMachine.file",
                "message": f"Missing referenced file: {manifest.stateMachine.file}",
            }
        )

    for agent in manifest.agents:
        agent_file = f"agents/{agent.name}.json"
        if not (bundle_root / agent_file).is_file():
            errors.append(
                {
                    "code": ERROR_AGENT_FILE_MISSING,
                    "location": f"agents.{agent.name}",
                    "message": f"Missing referenced file: {agent_file}",
                }
            )
        prompt_file = f"prompts/{agent.name}.md"
        if not (bundle_root / prompt_file).is_file():
            errors.append(
                {
                    "code": ERROR_PROMPT_FILE_MISSING,
                    "location": f"prompts.{agent.name}",
                    "message": f"Missing referenced file: {prompt_file}",
                }
            )

    for guard in manifest.guards:
        guard_file = f"guards/{guard.value}.json"
        if not (bundle_root / guard_file).is_file():
            errors.append(
                {
                    "code": ERROR_GUARD_FILE_MISSING,
                    "location": f"guards.{guard.value}",
                    "message": f"Missing referenced file: {guard_file}",
                }
            )
    errors.sort(key=lambda row: (row["code"], row["location"], row["message"]))
    return errors


def _bundle_archive_reference_errors(entry_names: set[str], manifest: OrketManifest) -> List[Dict[str, str]]:
    errors: List[Dict[str, str]] = []
    state_machine_file = str(manifest.stateMachine.file).replace("\\", "/")
    if state_machine_file not in entry_names:
        errors.append(
            {
                "code": ERROR_STATE_MACHINE_MISSING,
                "location": "stateMachine.file",
                "message": f"Missing referenced file: {state_machine_file}",
            }
        )

    for agent in manifest.agents:
        agent_file = f"agents/{agent.name}.json"
        if agent_file not in entry_names:
            errors.append(
                {
                    "code": ERROR_AGENT_FILE_MISSING,
                    "location": f"agents.{agent.name}",
                    "message": f"Missing referenced file: {agent_file}",
                }
            )
        prompt_file = f"prompts/{agent.name}.md"
        if prompt_file not in entry_names:
            errors.append(
                {
                    "code": ERROR_PROMPT_FILE_MISSING,
                    "location": f"prompts.{agent.name}",
                    "message": f"Missing referenced file: {prompt_file}",
                }
            )

    for guard in manifest.guards:
        guard_file = f"guards/{guard.value}.json"
        if guard_file not in entry_names:
            errors.append(
                {
                    "code": ERROR_GUARD_FILE_MISSING,
                    "location": f"guards.{guard.value}",
                    "message": f"Missing referenced file: {guard_file}",
                }
            )

    errors.sort(key=lambda row: (row["code"], row["location"], row["message"]))
    return errors


def validate_bundle(
    target: Path,
    *,
    engine_version: str = "",
    available_models: List[str] | None = None,
    model_override: str = "",
) -> Dict[str, Any]:
    manifest_path, bundle_root = _resolve_manifest_path(target)
    if manifest_path is None:
        return {
            "ok": False,
            "target": str(target),
            "error_count": 1,
            "errors": [
                {
                    "code": ERROR_MANIFEST_NOT_FOUND,
                    "location": "manifest",
                    "message": "Manifest not found. Expected one of: orket.yaml, orket.yml, orket.json",
                }
            ],
        }

    try:
        payload = _load_manifest_payload(manifest_path)
    except (ValueError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "target": str(target),
            "error_count": 1,
            "errors": [
                {
                    "code": ERROR_MANIFEST_PARSE,
                    "location": str(manifest_path.name),
                    "message": str(exc),
                }
            ],
        }

    try:
        manifest = OrketManifest.model_validate(payload)
    except ValidationError as exc:
        rows = _schema_validation_errors(exc)
        return {
            "ok": False,
            "target": str(target),
            "error_count": len(rows),
            "errors": rows,
        }

    rows = _bundle_reference_errors(bundle_root, manifest)
    effective_engine_version = str(engine_version or "").strip() or _current_engine_version()
    if not is_engine_compatible(manifest, effective_engine_version):
        rows.append(
            {
                "code": ERROR_ENGINE_INCOMPATIBLE,
                "location": "metadata.engineVersion",
                "message": (
                    f"Engine version {effective_engine_version} does not satisfy "
                    f"manifest range {manifest.metadata.engineVersion}."
                ),
            }
        )

    model_selection: Dict[str, Any] | None = None
    if available_models is not None or str(model_override or "").strip():
        model_selection = resolve_model_selection(
            manifest,
            available_models=list(available_models or []),
            model_override=str(model_override or ""),
        )
        if not bool(model_selection.get("ok")):
            rows.append(
                {
                    "code": str(model_selection.get("code") or "E_MODEL_SELECTION"),
                    "location": "model",
                    "message": str(model_selection.get("message") or "model selection failed"),
                }
            )

    rows.sort(key=lambda row: (row["code"], row["location"], row["message"]))
    if rows:
        result = {
            "ok": False,
            "target": str(target),
            "manifest_path": str(manifest_path),
            "manifest_name": manifest.metadata.name,
            "manifest_version": manifest.metadata.version,
            "engine_version_checked": effective_engine_version,
            "error_count": len(rows),
            "errors": rows,
        }
        if model_selection is not None:
            result["model_selection"] = model_selection
        return result

    result = {
        "ok": True,
        "target": str(target),
        "manifest_path": str(manifest_path),
        "manifest_name": manifest.metadata.name,
        "manifest_version": manifest.metadata.version,
        "engine_version_checked": effective_engine_version,
        "error_count": 0,
        "errors": [],
    }
    if model_selection is not None:
        result["model_selection"] = model_selection
    return result


def pack_bundle(source: Path, out_path: Path | None = None) -> Dict[str, Any]:
    if not source.is_dir():
        return {
            "ok": False,
            "target": str(source),
            "error_count": 1,
            "errors": [
                {
                    "code": ERROR_PACK_SOURCE_NOT_DIRECTORY,
                    "location": "source",
                    "message": "Pack source must be a directory containing an Orket manifest and assets.",
                }
            ],
        }

    validation = validate_bundle(source)
    if not bool(validation.get("ok")):
        return {
            "ok": False,
            "target": str(source),
            "error_count": 1,
            "errors": [
                {
                    "code": ERROR_PACK_VALIDATE_FAILED,
                    "location": "bundle",
                    "message": "Bundle must pass 'orket validate' before packing.",
                }
            ],
            "validation": validation,
        }

    manifest_path, _bundle_root = _resolve_manifest_path(source)
    assert manifest_path is not None
    payload = _load_manifest_payload(manifest_path)
    manifest = OrketManifest.model_validate(payload)
    destination = (
        out_path
        if out_path is not None
        else Path.cwd() / f"{manifest.metadata.name}-{manifest.metadata.version}.orket"
    )
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)

    source_files = sorted(path.resolve() for path in source.rglob("*") if path.is_file())
    entries: List[Tuple[Path, str]] = []
    for file_path in source_files:
        if file_path == destination:
            continue
        arcname = str(file_path.relative_to(source.resolve())).replace("\\", "/")
        if not _is_safe_archive_name(arcname):
            return {
                "ok": False,
                "target": str(source),
                "error_count": 1,
                "errors": [
                    {
                        "code": ERROR_PACK_UNSAFE_ARCHIVE_PATH,
                        "location": "archive",
                        "message": f"Unsafe archive path derived from source: {arcname}",
                    }
                ],
            }
        entries.append((file_path, arcname))

    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path, arcname in sorted(entries, key=lambda item: item[1]):
            info = zipfile.ZipInfo(filename=arcname, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o644 & 0xFFFF) << 16
            archive.writestr(info, file_path.read_bytes())

    return {
        "ok": True,
        "source": str(source),
        "output": str(destination),
        "manifest_name": manifest.metadata.name,
        "manifest_version": manifest.metadata.version,
        "file_count": len(entries),
        "error_count": 0,
        "errors": [],
    }


def inspect_target(target: Path) -> Dict[str, Any]:
    if not target.exists():
        return {
            "ok": False,
            "target": str(target),
            "error_count": 1,
            "errors": [
                {
                    "code": ERROR_INSPECT_TARGET_NOT_FOUND,
                    "location": "target",
                    "message": f"Target not found: {target}",
                }
            ],
        }

    if target.is_file() and target.suffix.lower() == ".orket":
        with zipfile.ZipFile(target, "r") as archive:
            names = sorted(name for name in archive.namelist() if not name.endswith("/"))
            manifest_name = next(
                (name for name in ("orket.yaml", "orket.yml", "orket.json") if name in names),
                None,
            )
            if manifest_name is None:
                return {
                    "ok": False,
                    "target": str(target),
                    "error_count": 1,
                    "errors": [
                        {
                            "code": ERROR_INSPECT_MANIFEST_NOT_FOUND,
                            "location": "archive",
                            "message": "Archive missing manifest: expected orket.yaml, orket.yml, or orket.json.",
                        }
                    ],
                }
            try:
                manifest_payload = _parse_manifest_content(
                    suffix=Path(manifest_name).suffix.lower(),
                    text=archive.read(manifest_name).decode("utf-8"),
                )
                manifest = OrketManifest.model_validate(manifest_payload)
            except (ValueError, ValidationError, json.JSONDecodeError) as exc:
                return {
                    "ok": False,
                    "target": str(target),
                    "error_count": 1,
                    "errors": [
                        {
                            "code": ERROR_MANIFEST_PARSE,
                            "location": manifest_name,
                            "message": str(exc),
                        }
                    ],
                }
            errors = _bundle_archive_reference_errors(set(names), manifest)
            if errors:
                return {
                    "ok": False,
                    "target": str(target),
                    "error_count": len(errors),
                    "errors": errors,
                }
            return _inspect_summary(
                target=str(target),
                manifest=manifest,
                manifest_path=manifest_name,
                entry_count=len(names),
            )

    validation = validate_bundle(target)
    if not bool(validation.get("ok")):
        return validation
    manifest_path, _bundle_root = _resolve_manifest_path(target)
    assert manifest_path is not None
    manifest = OrketManifest.model_validate(_load_manifest_payload(manifest_path))
    return _inspect_summary(
        target=str(target),
        manifest=manifest,
        manifest_path=str(manifest_path),
        entry_count=None,
    )


def _inspect_summary(
    *,
    target: str,
    manifest: OrketManifest,
    manifest_path: str,
    entry_count: int | None,
) -> Dict[str, Any]:
    summary = {
        "ok": True,
        "target": target,
        "manifest_path": manifest_path,
        "name": manifest.metadata.name,
        "version": manifest.metadata.version,
        "engineVersion": manifest.metadata.engineVersion,
        "model": {
            "preferred": manifest.model.preferred,
            "minimum": manifest.model.minimum,
            "fallback": list(manifest.model.fallback),
            "allowOverride": bool(manifest.model.allowOverride),
        },
        "permissions": {
            "filesystem_read_count": len(manifest.permissions.filesystem.read),
            "filesystem_write_count": len(manifest.permissions.filesystem.write),
            "network_allowed": bool(manifest.permissions.network.allowed),
            "tools_allowed_count": len(manifest.permissions.tools.allowed),
        },
        "agents_count": len(manifest.agents),
        "guards": [guard.value for guard in manifest.guards],
        "error_count": 0,
        "errors": [],
    }
    if entry_count is not None:
        summary["entry_count"] = entry_count
    return summary


def _is_safe_archive_name(name: str) -> bool:
    normalized = str(name or "").replace("\\", "/")
    if not normalized or normalized.startswith("/") or normalized.startswith("./"):
        return False
    pure = PurePosixPath(normalized)
    if pure.is_absolute():
        return False
    if ".." in pure.parts:
        return False
    return normalized == str(pure)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="orket", description="Orket bundle tools.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate an Orket manifest and bundle references.")
    validate_parser.add_argument("target", nargs="?", default=".", help="Bundle directory or manifest file path.")
    validate_parser.add_argument(
        "--engine-version",
        default=_current_engine_version(),
        help="Engine version used for compatibility checks.",
    )
    validate_parser.add_argument(
        "--available-model",
        action="append",
        default=[],
        help="Available model identifier. Repeatable.",
    )
    validate_parser.add_argument(
        "--model-override",
        default="",
        help="Requested model override for policy validation.",
    )
    validate_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")

    pack_parser = subparsers.add_parser("pack", help="Pack a validated Orket bundle into a .orket archive.")
    pack_parser.add_argument("source", nargs="?", default=".", help="Bundle directory path.")
    pack_parser.add_argument("--out", default="", help="Output .orket path.")
    pack_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")

    inspect_parser = subparsers.add_parser("inspect", help="Inspect an Orket bundle directory or .orket archive.")
    inspect_parser.add_argument("target", nargs="?", default=".", help="Bundle directory or .orket archive path.")
    inspect_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")

    refactor_parser = subparsers.add_parser("refactor", help="Run CP-1.1 transactional refactor (rename only).")
    refactor_parser.add_argument("instruction", help="Refactor instruction. Supported: rename <A> to <B>.")
    refactor_parser.add_argument("--scope", action="append", required=True, help="Write scope path (repeatable).")
    refactor_parser.add_argument("--yes", action="store_true", help="Confirm mutation execution.")
    refactor_parser.add_argument("--dry-run", action="store_true", help="Plan only, no writes.")
    refactor_parser.add_argument("--verify-profile", default="default", help="Verification profile from orket.config.json.")
    refactor_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")

    api_parser = subparsers.add_parser("api", help="API generation commands.")
    api_sub = api_parser.add_subparsers(dest="api_command", required=True)
    api_add = api_sub.add_parser("add", help="Generate one API route/controller/types set (v1 adapter).")
    api_add.add_argument("route_name", help="Route name (e.g. member).")
    api_add.add_argument("--schema", required=True, help="Schema fields, e.g. 'id:int,name:string'.")
    api_add.add_argument("--method", default="get", help="HTTP method.")
    api_add.add_argument("--scope", action="append", required=True, help="Write scope path (repeatable).")
    api_add.add_argument("--yes", action="store_true", help="Confirm mutation execution.")
    api_add.add_argument("--dry-run", action="store_true", help="Plan only, no writes.")
    api_add.add_argument("--verify-profile", default="default", help="Verification profile from orket.config.json.")
    api_add.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")

    init_parser = subparsers.add_parser("init", help="Generate scaffold from local blueprint templates.")
    init_parser.add_argument("template", help="Blueprint name (e.g. minimal-node).")
    init_parser.add_argument("project_name", help="Project name token for template hydration.")
    init_parser.add_argument("--dir", default="", help="Output directory path (defaults to ./<project_name>).")
    init_parser.add_argument("--vars", default="", help="Comma-separated key=value variables.")
    init_parser.add_argument("--no-verify", action="store_true", help="Skip post-generation verify commands.")
    init_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")
    return parser


def _parse_vars(raw: str) -> Dict[str, str]:
    values: Dict[str, str] = {}
    for token in [part.strip() for part in str(raw or "").split(",") if part.strip()]:
        key, sep, value = token.partition("=")
        if sep and key.strip():
            values[key.strip()] = value.strip()
    return values


def _render_human(result: Dict[str, Any]) -> str:
    if "code" in result and "message" in result:
        lines: List[str] = []
        if result.get("plan"):
            lines.append(str(result["plan"]))
        status = "OK" if bool(result.get("ok")) else f"FAIL [{result.get('code')}]"
        lines.append(f"{status}: {result.get('message')}")
        if result.get("verify_output_tail"):
            lines.append("")
            lines.append(str(result["verify_output_tail"]))
        return "\n".join(lines)

    if bool(result.get("ok")):
        return (
            f"OK: {result.get('manifest_name')} {result.get('manifest_version')} "
            f"({result.get('manifest_path')})"
        )
    lines = [f"FAIL ({result.get('error_count', 0)} error(s))"]
    for item in result.get("errors", []):
        lines.append(f"[{item.get('code')}] {item.get('location')}: {item.get('message')}")
    return "\n".join(lines)


def main(argv: List[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "validate":
        available_models = list(args.available_model or [])
        result = validate_bundle(
            Path(args.target),
            engine_version=str(args.engine_version),
            available_models=(available_models if available_models else None),
            model_override=str(args.model_override or ""),
        )
    elif args.command == "pack":
        out = Path(args.out) if str(args.out).strip() else None
        result = pack_bundle(Path(args.source), out_path=out)
    elif args.command == "inspect":
        result = inspect_target(Path(args.target))
    elif args.command == "refactor":
        result = run_refactor_transaction(
            instruction=str(args.instruction),
            scope_inputs=list(args.scope or []),
            dry_run=bool(args.dry_run),
            auto_confirm=bool(args.yes),
            verify_profile=str(args.verify_profile),
        )
    elif args.command == "api" and args.api_command == "add":
        result = run_api_add_transaction(
            route_name=str(args.route_name),
            schema_text=str(args.schema),
            method=str(args.method),
            scope_inputs=list(args.scope or []),
            dry_run=bool(args.dry_run),
            auto_confirm=bool(args.yes),
            verify_profile=str(args.verify_profile),
        )
    elif args.command == "init":
        result = run_scaffold_init(
            template_name=str(args.template),
            project_name=str(args.project_name),
            output_dir=(str(args.dir).strip() or None),
            variable_overrides=_parse_vars(str(args.vars or "")),
            verify_enabled=not bool(args.no_verify),
        )
    else:
        print(json.dumps({"ok": False, "error": "unsupported_command"}, ensure_ascii=False))
        return 2

    if bool(getattr(args, "json", False)):
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(_render_human(result))
    return 0 if bool(result.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
