# Controller Workload Phase 1 Bootstrap (SDK-First)

Last updated: 2026-03-08
Status: Active
Owner: Orket Core

## Summary
- Launch a new active lane for Controller Workload.
- Start with requirements-first packaging and an SDK-first contract seam.
- Confirm extension/runtime paths:
  1. Installed extension runtime copies: `.orket/durable/extensions/<extension>-<hash>`
  2. Extension catalog: `.orket/durable/config/extensions_catalog.json`
  3. Workload run artifacts: `workspace/extensions/<extension_id>/...`
  4. Phase bootstrap source layout: `extensions/controller_workload`

## Key Implementation Changes
1. Project bootstrap and authority wiring:
   - Add `docs/projects/controller-workload/` planning docs.
   - Add `controller-workload` to `docs/ROADMAP.md` Priority Now and Project Index.
   - Keep `CURRENT_AUTHORITY.md` unchanged unless canonical install/runtime/test paths change.
2. SDK-owned generic controller contract:
   - Add `orket_extension_sdk/controller.py`.
   - Export controller primitives from `orket_extension_sdk/__init__.py`.
3. Runtime enforcement and dispatch path:
   - Add controller dispatcher under `orket/extensions/`.
   - Enforce child execution through `ExtensionManager.run_workload`.
4. Control-surface defaults:
   - Runtime policy/env caps for max depth, max fanout, and child timeout.
   - Payload requests are clamped to runtime policy.
5. Hybrid extension source layout:
   - Add bootstrap source under `extensions/controller_workload/`.
   - Preserve external install path via `orket extensions install`.
6. Spec extraction before deep implementation:
   - Add `docs/specs/CONTROLLER_WORKLOAD_V1.md` before broad implementation.

## Test Plan
- `contract`: controller SDK dataclass/envelope validation and deterministic serialization.
- `integration`: controller dispatch through `ExtensionManager` to SDK child workloads.
- `integration`: cap enforcement for requested vs enforced depth/fanout/timeout.
- `integration`: SDK-only child restriction and stable denial codes.
- `integration`: recursion/cycle/depth violations deny deterministically.
- `integration`: provenance chain includes enforced caps, child order, and outcomes.
- `unit`: policy-cap resolver precedence and clamp behavior.
- `unit`: sequential child executor behavior on success/failure.

## Assumptions and Defaults
- Lane is active in `Priority Now`.
- Controller v0 executes children sequentially only.
- Controller v0 allows only SDK (`sdk_v0`) child workloads.
- Child execution always routes through `ExtensionManager`.
- Depth/fanout are payload-requested but runtime hard-capped.
- `extensions/controller_workload` is bootstrap authoring only; long-term target remains external extension packaging.
