# Orket SDK Project

Date: 2026-03-01

## Purpose

Formalize the extension SDK that lets external workloads run inside Orket with declared capabilities, deterministic execution, and artifact provenance. TextMystery is the reference consumer.

## Three-Layer Model

| Layer | Repo | Role |
|---|---|---|
| Orket | `c:\Source\Orket` | Engine, orchestration, reforger, extension manager |
| Orket SDK | `orket_extension_sdk/` (in-tree) | Extension contract: manifest, capabilities, workload, result |
| TextMystery | `c:\Source\Orket-Extensions\TextMystery` | Reference extension that drives SDK requirements |

TextMystery drives what the SDK needs. SDK may surface requirements for Orket.

## What Exists (as of 2026-03-01)

The SDK package (`orket_extension_sdk/`) is functional:

- `manifest.py` - ExtensionManifest + WorkloadManifest (Pydantic, YAML/JSON)
- `capabilities.py` - CapabilityRegistry with register/get/preflight + vocab
- `workload.py` - WorkloadContext + Workload protocol + run_workload()
- `result.py` - WorkloadResult with ok/output/artifacts/issues/metrics
- `testing.py` - Test harness utilities

Orket integration (`orket/extensions/`):

- `manager.py` - ExtensionManager: catalog, install, execute
- `workload_executor.py` - Runs both legacy and SDK workloads
- `workload_artifacts.py` - Builds capability registry, validates artifacts
- `manifest_parser.py` - Parses extension.yaml into ExtensionRecord
- `catalog.py` - Persistent extension catalog (JSON)
- `contracts.py` - Workload/RunPlan/ExtensionRegistry protocols
- `models.py` - Data classes (ExtensionRecord, WorkloadRecord, etc.)
- `reproducibility.py` - Git-clean enforcement for reliable mode

## Canonical Docs

1. `docs/projects/SDK/README.md` (this file)
2. `docs/projects/SDK/01-REQUIREMENTS.md`
3. `docs/projects/SDK/02-PLAN.md`
