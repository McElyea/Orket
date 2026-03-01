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

Audio integration additions:
- `orket_extension_sdk/audio.py` - `TTSProvider`, `AudioPlayer`, `AudioClip`, `VoiceInfo`, null implementations
- `orket/capabilities/tts_piper.py` - optional Piper-backed `TTSProvider`
- `orket/capabilities/audio_player.py` - optional `sounddevice` `AudioPlayer`
- `orket/reforger/routes/textmystery_persona_v0.py` - voice-profile normalization + validation

## Current Completion State

Completed in this repository:
- Phase 1 (typed capability providers)
- Phase 2 (Piper backend + fallback registration)
- Phase 3 bridge-path integration (`textmystery_bridge_v1`) with audio artifact output
- Phase 4 backend registration for audio playback (`sounddevice` + null fallback)
- Phase 5 reforger voice profile validation and digesting

Remaining scope is external:
- Direct TextMystery upstream repo content/render changes listed in `02-PLAN.md` remain out-of-tree from this repo.

## Canonical Docs

1. `docs/projects/SDK/README.md` (this file)
2. `docs/projects/SDK/01-REQUIREMENTS.md`
3. `docs/projects/SDK/02-PLAN.md`
