"""Application ownership of workload preparation and artifact/provenance workers."""
from __future__ import annotations

from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.storage.workload_artifact_store import digest_file, write_json_file

from .contracts import RunPlan, Workload
from .models import ExtensionRecord, _ExtensionManifestEntry
from .workload_artifacts import WorkloadArtifacts
from .workload_executor_support import compile_workload
from .workload_loader import WorkloadLoader
from .workload_policy import WorkloadPolicy


async def prepare_legacy_workload(
    loader: WorkloadLoader, artifacts: WorkloadArtifacts, extension: ExtensionRecord,
    workload: _ExtensionManifestEntry, input_config: dict[str, Any], interaction_context: Any | None,
    *, policy: WorkloadPolicy,
) -> tuple[Workload, RunPlan]:
    loaded = await run_owned_thread(partial(loader.load_legacy_workload, extension, workload.workload_id),
                                    label="legacy-extension-load")
    plan = await run_owned_thread(partial(compile_workload, loaded, input_config, interaction_context),
                                  label="legacy-workload-compile")
    if plan.workload_id != workload.workload_id:
        raise ValueError("RunPlan workload_id mismatch")

    def validate_materials() -> None:
        if policy.reliable_mode_enabled:
            artifacts.reproducibility.validate_required_materials(loaded.required_materials())

    await run_owned_thread(validate_materials, label="legacy-workload-materials")
    if policy.reliable_mode_enabled:
        await artifacts.reproducibility.validate_clean_git_if_required(required=policy.reliable_require_clean_git)
    return loaded, plan


async def publish_manifest(
    artifacts: WorkloadArtifacts, artifact_root: Path, *, plan_hash: str, governed_identity: dict[str, Any],
    policy: WorkloadPolicy,
) -> tuple[dict[str, Any], Path, str]:
    manifest = await run_owned_thread(partial(artifacts.build_artifact_manifest, artifact_root,
        plan_hash=plan_hash, governed_identity=governed_identity, policy=policy), label="workload-manifest-build")
    path = artifact_root / "artifact_manifest.json"
    await run_owned_thread(partial(write_json_file, path, manifest), label="workload-manifest-write")
    return manifest, path, f"sha256:{str(manifest.get('manifest_sha256') or '').strip()}"


async def publish_provenance(builder: Callable[[], dict[str, Any]], artifact_root: Path) -> tuple[Path, str]:
    provenance = await run_owned_thread(builder, label="workload-provenance-build")
    path = artifact_root / "provenance.json"
    await run_owned_thread(partial(write_json_file, path, provenance), label="workload-provenance-write")
    digest = await run_owned_thread(partial(digest_file, path), label="workload-provenance-digest")
    return path, digest
