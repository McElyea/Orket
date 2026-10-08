"""Worker-only publication of fresh local-agent example inputs and result projection."""
import json
from pathlib import Path

import yaml

from orket.adapters.execution.owned_io import require_sync_context
from orket.adapters.storage.verified_file import write_verified_bytes

side_effecting = True


def allocate_example(root: Path, target: Path) -> Path:
    require_sync_context(code="E_LOCAL_EXAMPLE_REQUIRES_NATIVE_OWNER")
    root, target = root.resolve(), target.resolve()
    if target == root or not target.is_relative_to(root):
        raise ValueError("E_LOCAL_EXAMPLE_PATH_OUTSIDE_PROJECT")
    target.mkdir(parents=True, exist_ok=False)
    return target


def publish_example_inputs(area: Path, request: bytes, continuation: bytes) -> None:
    require_sync_context(code="E_LOCAL_EXAMPLE_REQUIRES_NATIVE_OWNER")
    extension = area / "extension"
    manifest_path = extension / "extension.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    catalog = {"extensions": [{
        "extension_id": manifest["extension_id"], "extension_version": manifest["extension_version"],
        "extension_api_version": "1.0.0", "source": "packaged-local-agent-example",
        "path": str(extension), "contract_style": "sdk_v0", "manifest_path": str(manifest_path),
        "allowed_stdlib_modules": manifest["allowed_stdlib_modules"], "manifest_entries": manifest["workloads"],
    }]}
    for name, content in (("request.json", request), ("continuation.json", continuation),
                           ("catalog.json", json.dumps(catalog, ensure_ascii=False, indent=2).encode("utf-8"))):
        write_verified_bytes(area / name, content, error_code="E_LOCAL_EXAMPLE_INPUT_UNVERIFIED")


def publish_example_result(area: Path, content: bytes) -> None:
    require_sync_context(code="E_LOCAL_EXAMPLE_REQUIRES_NATIVE_OWNER")
    write_verified_bytes(area / "report.json", content, error_code="E_LOCAL_EXAMPLE_RESULT_UNVERIFIED")
