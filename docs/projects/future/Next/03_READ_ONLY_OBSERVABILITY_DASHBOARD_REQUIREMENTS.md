# Read-Only Observability Dashboard Requirements

Last updated: 2026-04-07
Status: Future requirements draft
Owner: Orket Core

Related authority:
1. `docs/ARCHITECTURE.md`
2. `CURRENT_AUTHORITY.md`
3. `docs/specs/RUN_EVIDENCE_GRAPH_V1.md`
4. `docs/architecture/event_taxonomy.md`
5. `scripts/observability/emit_run_evidence_graph.py`
6. `scripts/governance/build_runtime_truth_dashboard_seed.py`

## Posture

This is a future requirements draft, not active roadmap execution authority.

The first implementation slice should make existing runtime evidence easier to inspect. It must remain read-only and projection-only, and it must not become a new source of runtime truth.

## Problem

Orket already emits useful runtime evidence through runtime events, control-plane records, effect journal records, protocol ledger surfaces, run summaries, and run-evidence graph artifacts. Much of that evidence is still inspected through raw JSON, SQLite queries, or CLI scripts. A local dashboard can improve debugging and benchmarking only if it preserves authority boundaries and refuses to invent coherence from malformed evidence.

## Goals

1. Provide a local read-only dashboard for inspecting existing runtime evidence.
2. Show run status, recent runs, selected run evidence, effect/control-plane summaries, and relevant artifact links from canonical sources.
3. Clearly label all dashboard data as projection-only.
4. Fail closed or show explicit degraded states for missing, malformed, or contradictory inputs.
5. Avoid adding write operations, hidden state, or a parallel runtime authority surface.

## Non-Goals

1. Do not add card mutation, approval resolution, run start, or run cancel actions.
2. Do not create portfolio analytics or benchmark trend productization in the first slice.
3. Do not replace `run_evidence_graph.json`, run ledgers, control-plane records, or runtime event artifacts.
4. Do not infer execution success from logs or prose.
5. Do not add a separate frontend authority service.

## Requirements

1. The dashboard must be read-only for the first slice.
2. Every displayed runtime-truth row must identify its source surface, such as control-plane records, run ledger projection, runtime events, effect journal records, or run-evidence graph artifacts.
3. The UI must label projected data as `projection_only` where the underlying source is a projection.
4. The UI must show degraded or blocked states when source payloads fail validation.
5. The dashboard must not write to cards, sessions, approvals, run ledgers, protocol ledgers, control-plane stores, runtime settings, or benchmark publication indexes.
6. The dashboard may use FastAPI routes, static HTML, or generated HTML, but it must preserve existing API authentication rules if exposed through the API runtime.
7. The dashboard must not duplicate existing graph validation logic; it must consume the canonical validators or existing artifact readers.
8. The first slice must include a run-detail view that can link or embed the existing `run_evidence_graph.html` output when available.
9. The first slice must include an explicit empty-state and malformed-state display so missing proof is not confused with green status.
10. If dashboard routing changes the public API surface, the related source-of-truth docs must be updated in the same change.

## Acceptance Proof

Required proof:
1. Contract tests for source payload validation and projection labels.
2. Integration tests for read-only dashboard routes or generated output using seeded runtime evidence.
3. Negative tests for missing, malformed, or contradictory source payloads.
4. Test or code proof that dashboard routes do not call write methods on cards, settings, ledgers, or control-plane repositories.

Proof classification:
1. Projection labeling: contract proof.
2. Dashboard route or generated HTML rendering: integration proof.
3. No-write behavior: integration or structural proof, with structural proof clearly labeled if used.

Completion must report observed path as `primary`, `fallback`, `degraded`, or `blocked`, and observed result as `success`, `failure`, `partial success`, or `environment blocker`.
