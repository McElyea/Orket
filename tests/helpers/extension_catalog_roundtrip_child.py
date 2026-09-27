"""Owned child phases for installed SDK catalog round-trip proof."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from dataclasses import asdict
from functools import partial
from pathlib import Path
from typing import Any

import extension_catalog_roundtrip_profiles as profiles_module
import log_process_receipts as process_receipts_module
import psutil

import orket
import orket.extensions.manager as manager_module
from orket.adapters.execution.owned_io import run_owned_thread
from orket.application.services.command_process_supervisor import CommandProcessSupervisor
from orket.application.services.extension_catalog_commands import (
    list_installed_extensions,
    prepare_extension_manager,
)

CATALOG_SCALARS = (
    "extension_id", "extension_version", "extension_api_version", "source", "path", "module",
    "register_callable", "contract_style", "manifest_path", "resolved_commit_sha", "manifest_digest_sha256",
    "source_ref", "trust_profile", "installed_at_utc", "security_mode", "security_profile",
    "security_policy_version", "compat_fallbacks", "config_sections", "allowed_stdlib_modules",
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("install", "restart"))
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--durable-root", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--expected-import-root", required=True)
    parser.add_argument("--expected-interpreter", required=True)
    parser.add_argument("--profile", required=True, choices=sorted(profiles_module.PROFILES))
    return parser.parse_args()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _path_row(path: Path, *, include_payload: bool = False) -> dict[str, Any]:
    raw = path.read_bytes()
    row: dict[str, Any] = {"path": str(path), "sha256": _sha256_bytes(raw), "size": len(raw)}
    if include_payload:
        row["payload"] = json.loads(raw.decode("utf-8"))
    return row


def _result_row(command: list[str], result: Any) -> dict[str, Any]:
    return {
        "command": command,
        "returncode": result.returncode,
        "stdout_sha256": _sha256_bytes(result.stdout),
        "stderr_sha256": _sha256_bytes(result.stderr),
        **result.lifetime(),
    }


def _pid_readback(receipts: list[tuple[list[str], Any]]) -> list[dict[str, Any]]:
    indexed: list[tuple[int, str, int]] = []
    identities: dict[int, float | None] = {}
    for index, (_command, result) in enumerate(receipts):
        for role, pid in (
            ("transport", result.transport_pid),
            ("supervisor", result.supervisor_pid),
            ("command", result.command_pid),
        ):
            if pid is None:
                continue
            indexed.append((index, role, pid))
            identities[pid] = None
    observed = process_receipts_module.process_readback(identities)
    rows = [
        {"receipt": index, "role": role, "pid": pid, **observed[str(pid)]}
        for index, role, pid in indexed
    ]
    assert rows and all(row["status"] == "absent" for row in rows), rows
    return rows


def _install_physical(
    source: Path, checkout: Path, catalog: Path, installed: Any,
    profile: profiles_module.CatalogRoundtripProfile,
) -> dict[str, Any]:
    installed = json.loads(json.dumps(asdict(installed)))
    files = {}
    for relative in profile.source_files:
        source_row = _path_row(source / relative)
        checkout_row = _path_row(checkout / relative)
        assert source_row["sha256"] == checkout_row["sha256"]
        assert source_row["size"] == checkout_row["size"]
        files[relative] = {"source": source_row, "checkout": checkout_row}
    catalog_row = _path_row(catalog, include_payload=True)
    payload = catalog_row["payload"]
    assert type(payload) is dict and set(payload) == {"extensions"}
    assert type(payload["extensions"]) is list and len(payload["extensions"]) == 1
    row = payload["extensions"][0]
    assert type(row) is dict and set(row) == {*CATALOG_SCALARS, "manifest_entries"}
    assert {name: row[name] for name in CATALOG_SCALARS} == {
        name: installed[name] for name in CATALOG_SCALARS
    }
    assert row["extension_id"] == profile.extension_id
    assert row["extension_version"] == profile.extension_version
    assert row["source"] == str(source) and row["path"] == str(checkout)
    assert row["module"] == row["register_callable"] == "" and row["contract_style"] == "sdk_v0"
    assert type(row["manifest_entries"]) is list and len(row["manifest_entries"]) == 1
    raw_entry, installed_entry = row["manifest_entries"][0], installed["manifest_entries"][0]
    assert type(raw_entry) is dict and set(raw_entry) == set(profile.catalog_entry_fields)
    assert raw_entry == {name: installed_entry[name] for name in profile.catalog_entry_fields}
    assert raw_entry["workload_id"] == profile.workload_id
    assert raw_entry["entrypoint"] == profile.entrypoint
    assert installed_entry["input_contract"] == profile.input_contract
    assert installed_entry["output_contract"] == profile.output_contract
    assert raw_entry["required_capabilities"] == [] and raw_entry["contract_style"] == "sdk_v0"
    manifest = files["extension.json"]["checkout"]
    assert installed["manifest_digest_sha256"] == manifest["sha256"]
    assert Path(installed["manifest_path"]) == Path(installed["path"]) / "extension.json"
    return {"files": files, "catalog": catalog_row}


def _parser_record(parser: Any, installed: Any) -> dict[str, Any]:
    checkout = Path(installed.path)
    loaded = parser.load_manifest(checkout)
    parsed = parser.record_from_manifest(
        loaded.payload,
        source=installed.source,
        path=checkout,
        contract_style=loaded.contract_style,
        manifest_path=loaded.manifest_path,
        resolved_commit_sha=installed.resolved_commit_sha,
        manifest_digest_sha256=installed.manifest_digest_sha256,
        source_ref=installed.source_ref,
        trust_profile=installed.trust_profile,
        installed_at_utc=installed.installed_at_utc,
        security_mode=installed.security_mode,
        security_profile=installed.security_profile,
        security_policy_version=installed.security_policy_version,
        compat_fallbacks=installed.compat_fallbacks,
    )
    return asdict(parsed)


def _run_physical(result: dict[str, Any]) -> dict[str, Any]:
    artifact_root = Path(result["artifact_root"])
    artifact = _path_row(artifact_root / "json_result.txt")
    artifact["text"] = (artifact_root / "json_result.txt").read_text(encoding="utf-8")
    manifest = _path_row(Path(result["artifact_manifest_path"]), include_payload=True)
    provenance = _path_row(Path(result["provenance_path"]), include_payload=True)
    return {"artifact": artifact, "artifact_manifest": manifest, "provenance": provenance}


async def _install(arguments: argparse.Namespace, bootstrap: dict[str, Any]) -> dict[str, Any]:
    profile = bootstrap["profile"]
    manager = await prepare_extension_manager(
        catalog_path=arguments.catalog,
        project_root=arguments.project_root,
        invocation_root=arguments.project_root,
        environment=bootstrap["environment"],
    )
    assert manager.install_root == arguments.durable_root / "extensions"
    receipts: list[tuple[list[str], Any]] = []
    original = CommandProcessSupervisor.run

    async def observe(owner, argv, **kwargs):
        result = await original(owner, argv, **kwargs)
        receipts.append(([str(item) for item in argv], result))
        return result

    CommandProcessSupervisor.run = observe
    try:
        installed = await manager.install_from_repo(str(arguments.source))
    finally:
        CommandProcessSupervisor.run = original
    assert len(receipts) == 3
    expected_backend = "windows_job" if os.name == "nt" else "linux_subreaper"
    assert all(
        result.returncode == 0
        and result.reason == "completed"
        and result.cleanup_confirmed
        and result.capture_complete
        and result.backend == expected_backend
        for _command, result in receipts
    )
    pid_readback = await run_owned_thread(
        partial(_pid_readback, receipts), label="extension-catalog-install-pid-readback",
    )
    records = await list_installed_extensions(manager)
    selected = [row for row in records if row.extension_id == installed.extension_id]
    assert len(selected) == 1
    assert installed.contract_style == "sdk_v0"
    assert installed.resolved_commit_sha == arguments.expected_commit
    parser_record = await run_owned_thread(
        partial(_parser_record, manager.manifest_parser, installed),
        label="extension-catalog-install-parser-readback",
    )
    installed_record = asdict(installed)
    assert parser_record == installed_record
    physical = await run_owned_thread(
        partial(
            _install_physical, arguments.source, Path(installed.path), arguments.catalog, installed, profile,
        ),
        label="extension-catalog-install-physical-readback",
    )
    return {
        "parser_record": parser_record,
        "installed_record": installed_record,
        "same_manager_records": [asdict(row) for row in selected],
        "all_same_manager_records": [asdict(row) for row in records],
        "git_receipts": [_result_row(command, result) for command, result in receipts],
        "git_pid_readback": pid_readback,
        "physical": physical,
    }


async def _restart(arguments: argparse.Namespace, bootstrap: dict[str, Any]) -> dict[str, Any]:
    profile = bootstrap["profile"]
    manager = await prepare_extension_manager(
        catalog_path=arguments.catalog,
        project_root=arguments.project_root,
        invocation_root=arguments.project_root,
        environment=bootstrap["environment"],
    )
    records = await list_installed_extensions(manager)
    selected = [row for row in records if row.extension_id == profile.extension_id]
    assert len(selected) == 1
    result = await manager.run_workload(
        workload_id=profile.workload_id,
        input_config=profiles_module.sdk_input(),
        workspace=arguments.workspace,
        department="core",
        require_sdk=True,
    )
    payload = asdict(result)
    physical = await run_owned_thread(
        partial(_run_physical, payload), label="extension-catalog-restart-physical-readback",
    )
    return {
        "records": [asdict(row) for row in selected],
        "all_records": [asdict(row) for row in records],
        "run": payload,
        "physical": physical,
    }


def _bootstrap() -> tuple[argparse.Namespace, dict[str, Any]]:
    arguments = _arguments()
    for name in ("catalog", "project_root", "durable_root", "source", "workspace"):
        setattr(arguments, name, Path(getattr(arguments, name)).resolve())
    import_root = Path(orket.__file__).resolve().parent.parent
    manager_origin = Path(manager_module.__file__).resolve()
    process_receipts_origin = Path(process_receipts_module.__file__).resolve()
    profiles_origin = Path(profiles_module.__file__).resolve()
    assert process_receipts_origin == Path(__file__).resolve().with_name("log_process_receipts.py")
    assert profiles_origin == Path(__file__).resolve().with_name(
        "extension_catalog_roundtrip_profiles.py"
    )
    interpreter = Path(sys.executable).resolve()
    expected_root = Path(arguments.expected_import_root).resolve()
    assert import_root == expected_root
    assert manager_origin.is_relative_to(expected_root / "orket")
    assert interpreter == Path(arguments.expected_interpreter).resolve()
    identity = psutil.Process()
    environment = dict(os.environ, ORKET_DURABLE_ROOT=str(arguments.durable_root))
    profile = profiles_module.PROFILES[arguments.profile]
    return arguments, {
        "environment": environment,
        "profile": profile,
        "public": {
            "pid": identity.pid,
            "create_time": identity.create_time(),
            "interpreter": str(interpreter),
            "import_root": str(import_root),
            "manager_origin": str(manager_origin),
            "process_receipts_origin": str(process_receipts_origin),
            "profiles_origin": str(profiles_origin),
        },
    }


def main() -> int:
    arguments, bootstrap = _bootstrap()
    operation = _install if arguments.phase == "install" else _restart
    observed = asyncio.run(operation(arguments, bootstrap))
    payload = {
        "schema_version": "extension_catalog_roundtrip_child.v5",
        "phase": arguments.phase,
        "profile": arguments.profile,
        "bootstrap": bootstrap["public"],
        **observed,
    }
    sys.stdout.write(json.dumps(payload, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
