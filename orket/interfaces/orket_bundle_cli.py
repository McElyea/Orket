from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import yaml

from orket.application.services.bundle_service import BundleService
from orket.application.services.extension_scaffold_service import init_external_extension
from orket.application.services.governed_agent_admission import SUPPORTED_GOVERNED_AGENT_HOST_FEATURES
from orket.application.services.governed_run_demo_service import (
    DEFAULT_GOVERNED_RUN_SCENARIO,
    inspect_governed_run_bundle,
    is_governed_run_bundle,
    replay_governed_run_bundle,
    run_governed_run_scenario,
)
from orket.interfaces import bundle_cli_arguments, bundle_outward_cli, bundle_review_cli
from orket.interfaces.api_generation import run_api_add_transaction
from orket.interfaces.bundle_cli_output import emit_result, render_human
from orket.interfaces.governed_agent_cli import handle_governed_agent_command
from orket.interfaces.refactor_transaction import run_refactor_transaction
from orket.interfaces.scaffold_init import run_scaffold_init
from orket.reforger.cli import handle_reforge
from orket_extension_sdk import __version__ as sdk_version
from orket_extension_sdk.validate import validate_extension as validate_sdk_extension_tool

ERROR_SDK_COMMAND_REQUIRED = "E_SDK_COMMAND_REQUIRED"
ERROR_SDK_MANIFEST_NOT_FOUND = "E_SDK_MANIFEST_NOT_FOUND"
ERROR_SDK_ENTRYPOINT_INVALID = "E_SDK_ENTRYPOINT_INVALID"
ERROR_SDK_ENTRYPOINT_MISSING = "E_SDK_ENTRYPOINT_MISSING"
ERROR_GOVERNED_RUN_FAILED = "E_GOVERNED_RUN_FAILED"


def validate_sdk_extension(target: Path, *, strict: bool = False) -> dict[str, Any]:
    return validate_sdk_extension_tool(target, strict=strict, include_import_scan=False)


def validate_external_extension(target: Path, *, strict: bool = False) -> dict[str, Any]:
    return validate_sdk_extension_tool(
        target,
        strict=strict,
        include_import_scan=True,
        host_supported_features=SUPPORTED_GOVERNED_AGENT_HOST_FEATURES,
    )


def _print_governed_result(result: dict[str, Any], *, emit_json: bool) -> int:
    if emit_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(str(result.get("console_output") or render_human(result)))
    return 0 if bool(result.get("ok")) else 1


def _governed_run_error(exc: BaseException) -> dict[str, Any]:
    return {
        "kind": "governed_run_error",
        "ok": False,
        "code": ERROR_GOVERNED_RUN_FAILED,
        "message": str(exc),
    }


def _handle_governed_run_scenario(args: argparse.Namespace) -> int:
    try:
        result = asyncio.run(
            run_governed_run_scenario(
                Path(str(getattr(args, "scenario", DEFAULT_GOVERNED_RUN_SCENARIO))),
                workspace_root=Path(str(getattr(args, "workspace", "") or ".")),
            )
        )
    except (OSError, ValueError, TypeError, json.JSONDecodeError, yaml.YAMLError) as exc:
        result = _governed_run_error(exc)
    return _print_governed_result(result, emit_json=bool(getattr(args, "json", False)))


def _handle_demo_command(args: argparse.Namespace) -> int:
    command = str(getattr(args, "demo_command", "") or "").strip()
    if command == "local-agent":
        from orket.interfaces.local_agent_example_cli import handle_local_agent_example
        return handle_local_agent_example(args)
    if command != "governed-run":
        result = _governed_run_error(ValueError("Unsupported demo command"))
        return _print_governed_result(result, emit_json=bool(getattr(args, "json", False)))
    return _handle_governed_run_scenario(args)


def _handle_replay_command(args: argparse.Namespace) -> int:
    try:
        result = asyncio.run(replay_governed_run_bundle(Path(str(args.target))))
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        result = _governed_run_error(exc)
    if bool(getattr(args, "json", False)):
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(render_human(result))
    return 0 if bool(result.get("ok")) else 1


def _parse_vars(raw: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for token in [part.strip() for part in str(raw or "").split(",") if part.strip()]:
        key, sep, value = token.partition("=")
        if sep and key.strip():
            values[key.strip()] = value.strip()
    return values


def _handle_bundle_command(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "validate":
        available_models = list(args.available_model or [])
        result = asyncio.run(BundleService(engine_version=str(args.engine_version)).validate(
            Path(args.target),
            available_models=(available_models if available_models else None),
            model_override=str(args.model_override or ""),
        ))
    elif args.command == "pack":
        out = Path(args.out) if str(args.out).strip() else None
        result = asyncio.run(BundleService().pack(Path(args.source), out_path=out))
    elif args.command == "inspect":
        target = Path(args.target)
        if is_governed_run_bundle(target):
            try:
                result = asyncio.run(inspect_governed_run_bundle(target))
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
                result = _governed_run_error(exc)
        else:
            result = asyncio.run(BundleService().inspect(target))
    return result


def _handle_sdk_command(args: argparse.Namespace) -> dict[str, Any]:
    if str(getattr(args, "sdk_command", "")).strip() == "validate":
        result = validate_sdk_extension(Path(args.target), strict=bool(args.strict))
        for item in result.get("warnings", []):
            print(
                f"[{item.get('code')}] {item.get('location')}: {item.get('message')}",
                file=sys.stderr,
            )
    elif bool(args.version):
        result = {"ok": True, "sdk_version": sdk_version}
    else:
        result = {
            "ok": False,
            "error_count": 1,
            "errors": [
                {
                    "code": ERROR_SDK_COMMAND_REQUIRED,
                    "location": "sdk",
                    "message": "Specify an SDK command. Supported: 'orket sdk --version'.",
                }
            ],
        }
    return result


def _handle_extension_command(args: argparse.Namespace) -> dict[str, Any]:
    ext_command = str(getattr(args, "ext_command", "")).strip()
    if ext_command == "validate":
        result = validate_external_extension(Path(args.target), strict=bool(args.strict))
        for item in result.get("warnings", []):
            print(
                f"[{item.get('code')}] {item.get('location')}: {item.get('message')}",
                file=sys.stderr,
            )
    elif ext_command == "init":
        result = init_external_extension(
            Path(args.target),
            force=bool(args.force),
            template_kind=str(args.kind),
        )
    else:
        result = {
            "ok": False,
            "error_count": 1,
            "errors": [
                {
                    "code": "E_EXT_COMMAND_REQUIRED",
                    "location": "ext",
                    "message": "Specify an extension command. Supported: 'orket ext validate'.",
                }
            ],
        }
    return result


def _handle_generation_command(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == 'refactor':
        result = run_refactor_transaction(
            instruction=str(args.instruction),
            scope_inputs=list(args.scope or []),
            dry_run=bool(args.dry_run),
            auto_confirm=bool(args.yes),
            verify_profile=str(args.verify_profile),
        )
    elif args.command == 'api' and args.api_command == 'add':
        result = run_api_add_transaction(
            route_name=str(args.route_name),
            schema_text=str(args.schema),
            method=str(args.method),
            scope_inputs=list(args.scope or []),
            dry_run=bool(args.dry_run),
            auto_confirm=bool(args.yes),
            verify_profile=str(args.verify_profile),
        )
    elif args.command == 'init':
        result = run_scaffold_init(
            template_name=str(args.template),
            project_name=str(args.project_name),
            output_dir=(str(args.dir).strip() or None),
            variable_overrides=_parse_vars(str(args.vars or "")),
            verify_enabled=not bool(args.no_verify),
        )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = bundle_cli_arguments.build_parser()
    args, runtime_args = parser.parse_known_args(argv)
    if args.command == "setup":
        from orket.interfaces.setup_cli import main as setup_main
        return setup_main(runtime_args)
    if args.command == "doctor":
        from orket.interfaces.doctor_cli import main as doctor_main
        return doctor_main(runtime_args)
    if args.command == "runtime":
        parser.error("runtime must be invoked through the installed 'orket' command root")
    if runtime_args:
        parser.error(f"unrecognized arguments: {' '.join(runtime_args)}")
    if args.command in {"validate", "pack", "inspect"}:
        result = _handle_bundle_command(args)
    elif args.command == "demo":
        return _handle_demo_command(args)
    elif args.command == "sdk":
        result = _handle_sdk_command(args)
    elif args.command == "ext":
        result = _handle_extension_command(args)
    elif args.command in {"refactor", "init"} or (args.command == "api" and args.api_command == "add"):
        result = _handle_generation_command(args)
    elif args.command == "review":
        return bundle_review_cli.handle_review_command(args)
    elif args.command == "reforge":
        return handle_reforge(args)
    elif args.command == "run":
        if str(getattr(args, "run_command", "") or "").strip() == "scenario":
            return _handle_governed_run_scenario(args)
        return bundle_outward_cli.handle_run_command(args)
    elif args.command == "replay":
        return _handle_replay_command(args)
    elif args.command == "approvals":
        return bundle_outward_cli.handle_approvals_command(args)
    elif args.command == "ledger":
        return bundle_outward_cli.handle_ledger_command(args)
    elif args.command == "connectors":
        return bundle_outward_cli.handle_connectors_command(args)
    elif args.command == "agent":
        return handle_governed_agent_command(args)
    else:
        print(json.dumps({"ok": False, "error": "unsupported_command"}, ensure_ascii=False))
        return 2

    return emit_result(result, emit_json=bool(getattr(args, "json", False)))


if __name__ == "__main__":
    raise SystemExit(main())
