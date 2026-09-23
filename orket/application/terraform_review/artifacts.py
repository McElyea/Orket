from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from orket.adapters.storage.async_file_tools import AsyncFileTools, capture_file_roots

from .models import ArtifactBundle, canonical_digest


async def write_artifact_bundle(
    *,
    workspace: Path,
    execution_trace_ref: str,
    payloads: dict[str, dict[str, Any]],
) -> ArtifactBundle:
    workspace, = capture_file_roots([workspace])
    payloads = deepcopy(payloads)
    fs = AsyncFileTools(workspace)
    safe_trace_ref = execution_trace_ref.replace("\\", "-").replace("/", "-").strip() or "terraform-plan-review"
    artifact_root = Path("terraform_plan_reviews") / safe_trace_ref
    artifact_paths: dict[str, str] = {}
    artifact_hashes: dict[str, str] = {}

    for name, payload in payloads.items():
        rel_path = (artifact_root / f"{name}.json").as_posix()
        artifact_paths[name] = str(await fs.resolve_path_async(rel_path, write=True))
        artifact_hashes[name] = canonical_digest(payload)
        await fs.write_file(rel_path, payload)

    artifact_dir = str(await fs.resolve_path_async(artifact_root.as_posix(), write=True))
    manifest = {
        "artifact_dir": artifact_dir,
        "artifact_paths": dict(artifact_paths),
        "artifact_hashes": dict(artifact_hashes),
    }
    await fs.write_file((artifact_root / "manifest.json").as_posix(), manifest)
    artifact_paths["manifest"] = str(await fs.resolve_path_async((artifact_root / "manifest.json").as_posix(), write=True))
    artifact_hashes["manifest"] = canonical_digest(manifest)
    return ArtifactBundle(
        artifact_dir=artifact_dir,
        artifact_paths=artifact_paths,
        artifact_hashes=artifact_hashes,
    )
