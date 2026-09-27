"""Integration: an installed SDK record survives public list and process restart."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any

import pytest

import orket
from orket.adapters.execution.owned_io import run_owned_thread
from orket.application.services.command_process_supervisor import CommandProcessSupervisor
from orket.core.contracts.owned_command import OwnedCommandResult
from tests.helpers.extension_catalog_roundtrip_observations import (
    difference_rows,
    rehash_paths,
)
from tests.helpers.extension_catalog_roundtrip_profiles import (
    NULL_PROFILE,
    CatalogRoundtripProfile,
    sdk_input,
)
from tests.helpers.log_process_receipts import process_readback
from tests.integration.test_extension_git_longpath_installation import GIT_ATTRIBUTES, _git
from tests.runtime.test_extension_manager import _init_sdk_extension_repo_json_manifest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
HELPER = Path(__file__).resolve().parents[1] / "helpers" / "extension_catalog_roundtrip_child.py"
ACTIVE_IMPORT_ROOT = Path(orket.__file__).resolve().parent.parent
ACTIVE_INTERPRETER = Path(sys.executable).resolve()
TARGET_DIFFERENCE_PATHS = {
    "$.register_callable", "$.manifest_entries[0].input_contract",
    "$.manifest_entries[0].output_contract",
}


def _prepare_source(fixture_root: Path) -> tuple[Path, str]:
    source = fixture_root / "source"
    source.mkdir(parents=True)
    (source / ".gitattributes").write_bytes(GIT_ATTRIBUTES)
    _init_sdk_extension_repo_json_manifest(source)
    return source, _git(source, "rev-parse", "HEAD")


def _owner_row(result: OwnedCommandResult) -> dict[str, Any]:
    return {
        "returncode": result.returncode,
        "stdout_base64": base64.b64encode(result.stdout).decode("ascii"),
        "stderr_base64": base64.b64encode(result.stderr).decode("ascii"),
        "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(result.stderr).hexdigest(),
        **result.lifetime(),
    }


def _assert_owner(result: OwnedCommandResult) -> None:
    assert result.reason == "completed", result.lifetime()
    assert result.returncode == 0 and result.cleanup_confirmed and result.capture_complete
    assert result.backend == ("windows_job" if os.name == "nt" else "linux_subreaper")
    if result.stderr:
        raise AssertionError({
            "stderr_sha256": hashlib.sha256(result.stderr).hexdigest(), "stderr_size": len(result.stderr),
        })


async def _process_observation(
    child: dict[str, Any], result: OwnedCommandResult, label: str,
) -> dict[str, Any]:
    identities = {
        pid: None
        for pid in (result.transport_pid, result.supervisor_pid, result.command_pid)
        if pid is not None
    }
    identity = child["bootstrap"]
    identities[identity["pid"]] = identity["create_time"]
    observed = await run_owned_thread(
        partial(process_readback, identities), label=f"extension-catalog-{label}-process-readback",
    )
    assert observed
    assert all(row["status"] in {"absent", "reused"} for row in observed.values()), observed
    return observed


def _child_command(
    phase: str, *, catalog: Path, project_root: Path, durable_root: Path,
    source: Path, expected_commit: str, workspace: Path, profile: CatalogRoundtripProfile,
) -> list[str]:
    return [
        sys.executable,
        str(HELPER),
        phase,
        "--catalog", str(catalog),
        "--project-root", str(project_root),
        "--durable-root", str(durable_root),
        "--source", str(source),
        "--expected-commit", expected_commit,
        "--workspace", str(workspace),
        "--expected-import-root", str(ACTIVE_IMPORT_ROOT),
        "--expected-interpreter", str(ACTIVE_INTERPRETER),
        "--profile", profile.name,
    ]


async def _run_phase(
    owner: CommandProcessSupervisor, phase: str, *, catalog: Path, project_root: Path,
    durable_root: Path, source: Path, expected_commit: str, workspace: Path,
    profile: CatalogRoundtripProfile,
) -> OwnedCommandResult:
    environment = dict(os.environ)
    environment["ORKET_DURABLE_ROOT"] = str(durable_root)
    environment["PYTHONPATH"] = str(ACTIVE_IMPORT_ROOT)
    return await owner.run(
        _child_command(
            phase,
            catalog=catalog,
            project_root=project_root,
            durable_root=durable_root,
            source=source,
            expected_commit=expected_commit,
            workspace=workspace,
            profile=profile,
        ),
        cwd=project_root,
        environment=environment,
        timeout_seconds=30,
        output_limit_bytes=256 * 1024,
    )


def _assert_child(
    child: dict[str, Any], phase: str, profile: CatalogRoundtripProfile,
) -> None:
    assert child["schema_version"] == "extension_catalog_roundtrip_child.v5"
    assert child["phase"] == phase and child["profile"] == profile.name
    bootstrap = child["bootstrap"]
    assert bootstrap["interpreter"] == str(ACTIVE_INTERPRETER)
    assert bootstrap["import_root"] == str(ACTIVE_IMPORT_ROOT)
    assert Path(bootstrap["manager_origin"]).is_relative_to(ACTIVE_IMPORT_ROOT / "orket")
    assert Path(bootstrap["process_receipts_origin"]) == HELPER.with_name("log_process_receipts.py").resolve()
    assert Path(bootstrap["profiles_origin"]) == HELPER.with_name(
        "extension_catalog_roundtrip_profiles.py"
    ).resolve()
    assert type(bootstrap["pid"]) is int and bootstrap["pid"] > 0
    assert type(bootstrap["create_time"]) in {int, float} and bootstrap["create_time"] > 0


def _assert_install(
    child: dict[str, Any], source_commit: str, profile: CatalogRoundtripProfile,
) -> None:
    installed, physical = child["installed_record"], child["physical"]
    assert child["parser_record"] == installed
    assert installed["contract_style"] == "sdk_v0"
    assert installed["resolved_commit_sha"] == source_commit
    assert len(child["same_manager_records"]) == 1
    assert len(child["all_same_manager_records"]) == 1
    assert len(child["git_receipts"]) == 3
    expected_backend = "windows_job" if os.name == "nt" else "linux_subreaper"
    for receipt in child["git_receipts"]:
        assert receipt["returncode"] == 0 and receipt["reason"] == "completed"
        assert receipt["cleanup_confirmed"] and receipt["capture_complete"]
        assert receipt["backend"] == expected_backend
        assert receipt["command"] and all(type(item) is str and item for item in receipt["command"])
    assert child["git_pid_readback"]
    assert all(row["status"] == "absent" for row in child["git_pid_readback"])
    entry = installed["manifest_entries"][0]
    assert entry["input_contract"] == profile.input_contract
    assert entry["output_contract"] == profile.output_contract
    for relative in profile.source_files:
        pair = physical["files"][relative]
        assert pair["source"]["sha256"] == pair["checkout"]["sha256"]
        assert pair["source"]["size"] == pair["checkout"]["size"]


def _governed_digest(payload: Any) -> str:
    raw = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _sdk_input_digest() -> str:
    raw = json.dumps(sdk_input(), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _assert_governed(
    run: dict[str, Any], physical: dict[str, Any], profile: CatalogRoundtripProfile,
) -> None:
    artifact, manifest_row, provenance_row = (
        physical["artifact"], physical["artifact_manifest"], physical["provenance"]
    )
    manifest, provenance = manifest_row["payload"], provenance_row["payload"]
    expected_plan = _sdk_input_digest()
    expected_policy = _governed_digest(provenance["governed_policy"])
    expected_control = _governed_digest(provenance["control_bundle"])
    assert run["plan_hash"] == expected_plan
    assert provenance["input_config_digest"] == expected_plan
    assert provenance["plan_hash"] == expected_plan
    assert provenance["input_config_redacted"]["payload_digest_sha256"] == expected_plan
    assert artifact["text"] == "seed=41;label=restart"
    assert manifest["files"] == [{"path": "json_result.txt", "sha256": artifact["sha256"]}]
    expected_manifest = hashlib.sha256(
        json.dumps(manifest["files"], sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assert manifest["manifest_sha256"] == expected_manifest
    assert run["artifact_manifest_hash"] == "sha256:" + expected_manifest
    assert run["provenance_hash"] == "sha256:" + provenance_row["sha256"]
    assert run["artifact_manifest_path"] == manifest_row["path"]
    assert run["provenance_path"] == provenance_row["path"]
    artifact_root = Path(run["artifact_root"])
    assert Path(artifact["path"]).parent == artifact_root
    assert Path(manifest_row["path"]).parent == artifact_root
    assert Path(provenance_row["path"]).parent == artifact_root
    assert run["claim_tier"] == "non_deterministic_lab_only"
    assert run["compare_scope"] == "extension_workload_provenance_family_v1"
    assert run["operator_surface"] == "extension_run_result_identity_v1"
    assert run["determinism_class"] == "workspace"
    assert run["policy_digest"] == expected_policy
    assert run["control_bundle_hash"] == expected_control
    assert provenance["claim_tier"] == run["claim_tier"]
    assert provenance["compare_scope"] == run["compare_scope"]
    assert provenance["operator_surface"] == "extension_provenance_v1"
    assert provenance["policy_digest"] == run["policy_digest"]
    assert provenance["control_bundle_hash"] == run["control_bundle_hash"]
    assert provenance["artifact_manifest_ref"] == "artifact_manifest.json"
    assert provenance["artifact_manifest_hash"] == run["artifact_manifest_hash"]
    assert provenance["provenance_ref"] == "provenance.json"
    assert provenance["artifact_manifest"] == manifest
    assert provenance["control_bundle"]["input_identity"] == expected_plan
    assert provenance["workload"]["workload_id"] == run["workload_id"]
    assert provenance["workload"]["workload_version"] == run["workload_version"]
    assert provenance["workload"]["entrypoint"] == profile.entrypoint
    assert provenance["workload"]["required_capabilities"] == []
    assert provenance["control_plane"] == run["control_plane"]
    assert provenance["control_plane_workload_record"] == run["control_plane_workload_record"]
    assert run["control_plane_workload_record"]["output_contract_ref"] == "extension_run_result_identity_v1"
    assert provenance["execution_state_authority"] == "control_plane_records"
    assert provenance["lane_output_execution_state_authoritative"] is False
    assert manifest["claim_tier"] == run["claim_tier"]
    assert manifest["compare_scope"] == run["compare_scope"]
    assert manifest["operator_surface"] == "extension_artifact_manifest_v1"
    assert manifest["policy_digest"] == run["policy_digest"]
    assert manifest["control_bundle_hash"] == run["control_bundle_hash"]
    assert manifest["plan_hash"] == run["plan_hash"]
    assert manifest["provenance_ref"] == "provenance.json"
    assert run["control_plane"]["execution_state_authority"] == "control_plane_records"
    assert run["control_plane"]["lane_output_execution_state_authoritative"] is False


def _assert_restart(
    child: dict[str, Any], fixture_root: Path, profile: CatalogRoundtripProfile,
) -> None:
    assert len(child["records"]) == 1 and len(child["all_records"]) == 1
    run = child["run"]
    assert run["extension_id"] == profile.extension_id
    assert run["workload_id"] == profile.workload_id
    assert run["summary"]["output"] == {"label": "restart", "seed": 41}
    assert Path(run["artifact_root"]).is_relative_to(fixture_root)
    for key in (
        "control_plane_run_id", "control_plane_attempt_id", "control_plane_start_step_id",
        "control_plane_checkpoint_id", "control_plane_final_truth_record_id",
    ):
        assert run["control_plane"][key]
    _assert_governed(run, child["physical"], profile)


async def _complete_observation(
    install: dict[str, Any], restart: dict[str, Any], observation: dict[str, Any],
) -> None:
    install_identity = install["bootstrap"]["pid"], install["bootstrap"]["create_time"]
    restart_identity = restart["bootstrap"]["pid"], restart["bootstrap"]["create_time"]
    assert install_identity != restart_identity
    installed, listed = install["installed_record"], install["same_manager_records"][0]
    differences = difference_rows(installed, listed)
    assert all(row["path"] in TARGET_DIFFERENCE_PATHS for row in differences), differences
    assert install["same_manager_records"] == restart["records"], "E_EXT_CATALOG_RESTART_READBACK_DRIFT"
    physical_hashes = await run_owned_thread(
        partial(rehash_paths, install, restart), label="extension-catalog-final-physical-readback",
    )
    observation.update(
        stage="complete_before_final_record_equality",
        physical_hashes=physical_hashes,
        representation_differences=differences,
    )


async def _observed_phase(
    observation: dict[str, Any], owner: CommandProcessSupervisor, phase: str, *,
    catalog: Path, project_root: Path, durable_root: Path, source: Path,
    expected_commit: str, workspace: Path, profile: CatalogRoundtripProfile,
) -> dict[str, Any]:
    result = await _run_phase(
        owner, phase, catalog=catalog, project_root=project_root, durable_root=durable_root,
        source=source, expected_commit=expected_commit, workspace=workspace, profile=profile,
    )
    observation[f"{phase}_owner"] = _owner_row(result)
    _assert_owner(result)
    child = json.loads(result.stdout)
    observation[f"{phase}_child"] = child
    observation[f"{phase}_process_readback"] = await _process_observation(
        child, result, f"{profile.name}-{phase}",
    )
    _assert_child(child, phase, profile)
    return child


async def _exercise_roundtrip(
    *, tmp_path_factory: Any, record_property: Any, profile: CatalogRoundtripProfile,
    source_factory: Callable[[Path], tuple[Path, str]], fixture_prefix: str,
    cancellation_event: str, property_name: str, label_prefix: str,
) -> dict[str, Any]:
    fixture_root = Path(await run_owned_thread(
        partial(tmp_path_factory.mktemp, fixture_prefix), label=f"{label_prefix}-fixture-root",
    ))
    source, source_commit = await run_owned_thread(
        partial(source_factory, fixture_root), label=f"{label_prefix}-source-fixture",
    )
    project_root, durable_root = fixture_root / "project", fixture_root / "durable"
    await run_owned_thread(
        partial(project_root.mkdir, parents=True), label=f"{label_prefix}-project-root",
    )
    catalog = project_root / "extensions_catalog.json"
    owner = CommandProcessSupervisor(fixture_root, cancellation_event=cancellation_event)
    observation: dict[str, Any] = {
        "schema_version": "extension_catalog_roundtrip_observation.v3",
        "fixture_root": str(fixture_root),
        "source_commit": source_commit,
        "profile": profile.name,
        "stage": "fixture_ready",
    }
    try:
        install = await _observed_phase(
            observation, owner, "install", catalog=catalog, project_root=project_root,
            durable_root=durable_root, source=source, expected_commit=source_commit,
            workspace=fixture_root / "unused-install-workspace", profile=profile,
        )
        _assert_install(install, source_commit, profile)
        observation["stage"] = "installer_terminal_and_reaped"
        restart = await _observed_phase(
            observation, owner, "restart", catalog=catalog, project_root=project_root,
            durable_root=durable_root, source=source, expected_commit=source_commit,
            workspace=fixture_root / "restart-workspace", profile=profile,
        )
        _assert_restart(restart, fixture_root, profile)
        await _complete_observation(install, restart, observation)
    finally:
        record_property(property_name, json.dumps(observation, sort_keys=True))
    return observation


# Layer: integration. Serial owned install and restart children exercise real Git and SDK execution.
async def test_generic_sdk_catalog_roundtrip_is_lossless_across_restart(
    tmp_path_factory, record_property,
):
    """An installed generic SDK record must retain every field through list and restart."""
    observation = await _exercise_roundtrip(
        tmp_path_factory=tmp_path_factory, record_property=record_property, profile=NULL_PROFILE,
        source_factory=_prepare_source, fixture_prefix="sdkroundtrip",
        cancellation_event="extension_catalog_probe_cancelled",
        property_name="extension_catalog_roundtrip_observation", label_prefix="extension-catalog",
    )
    install = observation["install_child"]
    assert [install["installed_record"]] == install["same_manager_records"], (
        "E_EXT_CATALOG_INSTALL_LIST_ROUNDTRIP_DRIFT"
    )
