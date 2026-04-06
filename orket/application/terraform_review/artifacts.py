from __future__ import annotations

from pathlib import Path
from typing import Any

from orket.adapters.storage.async_file_tools import AsyncFileTools

from .models import ArtifactBundle, canonical_digest


async def write_artifact_bundle(
    *,
    workspace: Path,
    execution_trace_ref: str,
    payloads: dict[str, dict[str, Any]],
) -> ArtifactBundle:
    fs = AsyncFileTools(workspace)
    safe_trace_ref = execution_trace_ref.replace("\\", "-").replace("/", "-").strip() or "terraform-plan-review"
    artifact_root = Path("terraform_plan_reviews") / safe_trace_ref
    artifact_paths: dict[str, str] = {}
    artifact_hashes: dict[str, str] = {}

    for name, payload in payloads.items():
        rel_path = (artifact_root / f"{name}.json").as_posix()
        artifact_paths[name] = str((workspace / rel_path).resolve())
        artifact_hashes[name] = canonical_digest(payload)
        await fs.write_file(rel_path, payload)

    manifest = {
        "artifact_dir": str((workspace / artifact_root).resolve()),
        "artifact_paths": dict(artifact_paths),
        "artifact_hashes": dict(artifact_hashes),
    }
    await fs.write_file((artifact_root / "manifest.json").as_posix(), manifest)
    artifact_paths["manifest"] = str((workspace / artifact_root / "manifest.json").resolve())
    artifact_hashes["manifest"] = canonical_digest(manifest)
    return ArtifactBundle(
        artifact_dir=str((workspace / artifact_root).resolve()),
        artifact_paths=artifact_paths,
        artifact_hashes=artifact_hashes,
    )
