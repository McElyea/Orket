# Contract Delta

## Summary
- Change title: Extension capability slice closure and projection-surface hardening
- Owner: Orket Core
- Date: 2026-04-23
- Affected contract(s): `docs/specs/EXTENSION_CAPABILITY_AUTHORIZATION_V1.md`, `docs/specs/CONTROLLER_WORKLOAD_V1.md`, `docs/specs/CONTROLLER_OBSERVABILITY_V1.md`, `docs/specs/REVIEW_RUN_V0.md`

## Delta
- Current behavior: the extension capability authorization contract and canonical audit artifact still described the shipped slice as model-plus-memory only, controller child/operator surfaces did not have durable spec language for projection-only framing, and the review-run contract did not document the checkpoint fields now returned through the `control_plane` projection.
- Proposed behavior: the shipped extension capability slice now normatively covers `speech.transcribe`, `tts.speak`, `audio.play`, `speech.play_clip`, and `voice.turn_control` alongside `model.generate`, `memory.query`, and `memory.write`, the canonical capability audit artifact now includes voice/audio/turn-control proof rows, controller child `artifact_refs` plus controller observability events now carry explicit projection-only framing with a fixed source, and the review-run `control_plane` projection now documents the checkpoint fields it may surface.
- Why this break is required now: the runtime seams were already implemented and proven on targeted paths, so leaving the durable contracts and canonical audit scope on the older narrower story would keep README-level drift alive and would understate the operator-facing projection boundary that the runtime now enforces.

## Migration Plan
1. Compatibility window: none for malformed controller or review projections; valid existing payloads remain valid.
2. Migration steps:
   - align extension capability documentation and audit generation with the shipped voice/audio/turn-control slice
   - keep controller child and observability surfaces projection-only and deterministic by documenting the fixed framing they now emit
   - document review-run checkpoint projection fields without widening review-lane artifact authority
3. Validation gates:
   - `python -m pytest -q tests/runtime/test_extension_capability_authorization.py tests/runtime/test_extension_components.py tests/runtime/test_controller_dispatcher.py tests/runtime/test_controller_observability.py tests/runtime/test_controller_replay_parity.py tests/application/test_execution_pipeline_cards_epic_control_plane.py tests/application/test_review_run_service.py tests/runtime/test_epic_run_orchestrator.py tests/scripts/test_build_extension_capability_audit.py`
   - `python scripts/extensions/build_extension_capability_audit.py --strict`

## Rollback Plan
1. Rollback trigger: targeted proof shows the widened extension slice, controller projection framing, or review checkpoint projection language is overstating current runtime behavior.
2. Rollback steps:
   - revert the widened extension capability contract scope and audit cases
   - revert the controller projection framing language if runtime surfaces stop emitting those fields deterministically
   - revert the review checkpoint projection wording if the review result surface no longer returns those fields from durable control-plane records
3. Data/state recovery notes: the extension capability audit artifact is rerunnable and diff-ledger backed; rollback requires no data migration.

## Versioning Decision
- Version bump type: additive contract clarification and proof-surface expansion
- Effective version/date: 2026-04-23
- Downstream impact: extension capability audit consumers now see additional voice/audio/turn-control rows, controller operator/observability consumers must preserve explicit projection framing, and review-run consumers may now rely on documented checkpoint fields when they are present in the returned `control_plane` projection
