# Core Pillars Milestones

Date: 2026-02-24

Canonical slice execution detail:
`docs/projects/core-pillars/08-DETAILED-SLICE-EXECUTION-PLAN.md`

## Status Snapshot
1. CP-1.1 Transaction Shell Foundation: completed.
2. CP-1.2 API Generation First Adapter: completed.
3. CP-1.3 Minimal Scaffolding Hydration: completed.
4. CP-2.1 Replay Artifact Recorder (Bounded): completed.
5. CP-2.2 Replay Comparator and Drift Gates: completed.
6. CP-2.3 Verified Refactor Integration: completed.
7. CP-3.1 Bucket D Failure Lessons Memory: completed.
8. CP-3.2 Stateful Memory/Agent Integration (Bounded Expansion): completed.
9. CP-3.3 Local Sovereignty and Offline Matrix: completed.
10. Core Pillars canonical slice map (CP-1 through CP-3.3): completed.
11. CP-4 WorkItem Runtime Refactor: active.

## CP-1 (P1): Safety and API Vertical Slice
1. Land command transaction shell and safety contracts (`A1`, `A2`, `A4`) first.
2. Deliver `orket api add` for initial supported framework(s) on existing repos.
3. Deliver deterministic route test templates (template packs, not model-invented test structure).
4. Deliver minimal `orket init` blueprint hydration baseline.
5. Produce scaffold/API artifacts under retention policy.

## CP-2 (P2): Trust Vertical Slice
1. Deliver runtime replay schema and artifact recorder outputs.
2. Keep replay bounded to recording/comparison; no global policy-engine behavior.
3. Add deterministic replay drift gate.
4. Deliver verified refactor workflow with parity checks.
5. Integrate trust outputs into CI quality lane.
6. Deliver pre-execution failure-lesson advisory retrieval.

## CP-3 (P3): State and Sovereignty Vertical Slice
1. Integrate vector memory with deterministic retrieval contract.
2. Add persistent personality bot runtime profile controls.
3. Deliver offline capability matrix and enforced tests.
4. Validate end-to-end local-only run path.
5. Land Bucket D failure-lesson memory D1-D4 acceptance tests.

## Completion Definition
1. Each milestone ends with green `pytest` sweep and architecture gates.
2. Each milestone updates roadmap status and artifact links.
3. No milestone is complete without reproducible command-level runbook steps.

## CP-4 (P1): WorkItem Runtime Refactor
1. Land profile-agnostic WorkItem contract with immutable identifiers and core state classes.
2. Freeze current hierarchy/flow as `legacy_cards_v1` profile.
3. Deliver `project_task_v1` profile as default with arbitrary depth support.
4. Move lifecycle policy to transition boundary gates and remove direct status mutation paths.
5. Deliver migration mapping and lossless fixture validation (Rock/Epic/Issue -> WorkItem).
6. Gate completion on deterministic parity and transition contract tests.
