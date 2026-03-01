# Extension SDK v0 Author Guide (10 Minutes)

Last updated: 2026-02-28

## Goal

Build and run a deterministic SDK workload through Orket using the public seam:

`Workload.run(ctx, input) -> WorkloadResult`

`TurnResult` is engine-internal and not part of the public extension contract.

## 1. Create the extension repo layout

```
my_extension/
  extension.yaml
  my_extension.py
```

## 2. Write `extension.yaml`

```yaml
manifest_version: v0
extension_id: my.extension
extension_version: 0.1.0
workloads:
  - workload_id: demo_v1
    entrypoint: my_extension:run_workload
    required_capabilities: []
```

## 3. Write workload code

```python
from __future__ import annotations

import hashlib
from pathlib import Path

from orket_extension_sdk import ArtifactRef, WorkloadResult


def run_workload(ctx, payload):
    out_path = Path(ctx.output_dir) / "result.txt"
    text = f"seed={ctx.seed};mode={payload.get('mode', 'basic')}"
    out_path.write_text(text, encoding="utf-8")
    digest = hashlib.sha256(out_path.read_bytes()).hexdigest()
    return WorkloadResult(
        ok=True,
        output={"mode": payload.get("mode", "basic")},
        artifacts=[ArtifactRef(path="result.txt", digest_sha256=digest, kind="text")],
    )
```

## 4. Install in Orket

1. Commit the extension repo.
2. Install with `ExtensionManager.install_from_repo(<repo-path-or-url>)`.
3. Confirm workload resolution with `ExtensionManager.resolve_workload("demo_v1")`.

## 5. Run the workload

Call `ExtensionManager.run_workload(...)` with:

1. `workload_id="demo_v1"`
2. `input_config` payload (include `seed` for deterministic replay)
3. `workspace` path
4. `department` string

Runtime outputs include:

1. `workspace/extensions/<extension_id>/<run-leaf>/provenance.json`
2. `workspace/extensions/<extension_id>/<run-leaf>/artifact_manifest.json`
3. Declared artifact files

## 6. Determinism checklist

1. Keep output and artifact content seed-driven and pure from wall-clock noise.
2. Ensure every artifact in `WorkloadResult.artifacts` exists and has a matching SHA-256 digest.
3. Keep workload logic dependent on declared capabilities and explicit input only.

## 7. Capability preflight

If a workload declares required capabilities, Orket fails closed before execution when missing:

`E_SDK_CAPABILITY_MISSING: <capability_id>`

Provide capabilities through runtime input/configuration according to deployment policy.
