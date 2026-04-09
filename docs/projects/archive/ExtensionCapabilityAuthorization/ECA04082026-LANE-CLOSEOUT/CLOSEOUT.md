# Extension Capability Authorization First Slice Closeout

Last updated: 2026-04-08
Status: Completed
Owner: Orket Core

Active durable authority:
1. `docs/specs/EXTENSION_CAPABILITY_AUTHORIZATION_V1.md`
2. `docs/architecture/event_taxonomy.md`
3. `CURRENT_AUTHORITY.md`
4. `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_VALIDATION_V1.md`
5. `docs/specs/TOOL_EXECUTION_GATE_V1.md`

Archived lane record:
1. `docs/projects/archive/ExtensionCapabilityAuthorization/ECA04082026-LANE-CLOSEOUT/EXTENSION_CAPABILITY_AUTHORIZATION_REQUIREMENTS.md`
2. `docs/projects/archive/ExtensionCapabilityAuthorization/ECA04082026-LANE-CLOSEOUT/EXTENSION_CAPABILITY_AUTHORIZATION_IMPLEMENTATION_PLAN.md`

## Outcome

The Extension Capability Authorization first slice is closed.

Completed in this lane:
1. the host now computes a `host_authorized_capability_registry_v1` authorization envelope before SDK subprocess execution
2. the child now revalidates that envelope before workload code executes and fails closed on `E_SDK_CAPABILITY_AUTHORIZATION_DRIFT`
3. `model.generate`, `memory.query`, and `memory.write` now enforce declared versus admitted authority at invocation time
4. runtime telemetry, provenance, and the canonical audit artifact now preserve declared, admitted, instantiated, and used capability truth distinctly
5. the active authority story now lives in durable specs plus `CURRENT_AUTHORITY.md`; the remaining non-archive project doc under `docs/projects/ExtensionCapabilityAuthorization/` is the separate future Tool Gate Enforcement draft

## Verification

Observed path: `primary`
Observed result: `success`

Executed proof:
1. `python -m pytest -q tests/runtime/test_extension_components.py`
2. `python -m pytest -q tests/runtime/test_extension_manager.py`
3. `python -m pytest -q tests/core/test_runtime_event_logging.py`
4. `python -m pytest -q tests/runtime/test_extension_capability_authorization.py`
5. `python -m pytest -q tests/scripts/test_build_extension_capability_audit.py`
6. `python scripts/extensions/build_extension_capability_audit.py --strict`
7. `python scripts/governance/check_docs_project_hygiene.py`

## Remaining Blockers Or Drift

1. None for the shipped first-slice scope.
2. Voice, TTS, audio, turn-control, and broader tool-gate closure remain outside this completed slice and require explicit future lane work before any broader runtime claim.
