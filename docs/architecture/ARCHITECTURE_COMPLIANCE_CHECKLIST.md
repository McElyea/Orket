# Architecture Compliance Checklist

Last updated: 2026-03-10  
Status: Active (transition-aware)

Use this checklist before merge for any change that touches runtime, orchestration, adapters, interfaces, or decision nodes.

## Usage

1. Record each check as `pass`, `partial`, or `fail`.
2. If `partial` or `fail`, include exact path(s) and reason.
3. If non-compliance is pre-existing, confirm the change did not widen it.
4. Treat `docs/ARCHITECTURE.md` as target-state authority and `Known Current Exceptions` as transition debt.

## Checks

### AC-01 Dependency Direction

Pass criteria:
1. No new dependency edges violate allowed flow:
   1. `interfaces -> application`
   2. `application -> core/adapters/decision_nodes`
   3. `adapters -> core`
   4. `decision_nodes -> core contracts`

Evidence:
1. Import diff review for touched files.
2. Any dependency check script outputs, if available.

### AC-02 Decision Node Purity

Pass criteria:
1. New/changed decision-node code does not add side effects.
2. No direct file/database/tool/external mutation from decision nodes.
3. No hidden cross-invocation mutable state.

Evidence:
1. Code diff shows structured input -> structured output behavior.
2. Tests cover observable decision contracts.

### AC-03 Explicit Input Contracts

Pass criteria:
1. Decision nodes receive required context via explicit structured inputs.
2. New/changed decision code does not introduce runtime-context reach-through for decision semantics.

Evidence:
1. Contract signatures and call sites in application orchestrators.

### AC-04 Deterministic Runtime Inputs

Pass criteria:
1. New/changed `core`/`application` paths do not introduce direct wall-clock/random identity generation for deterministic decisions.
2. Time/randomness is passed through explicit orchestrator inputs when needed.

Evidence:
1. Code scan for `time.time()`, `datetime.now()`, `uuid4()`, `random.*` in touched deterministic paths.

### AC-05 Side-Effect Ownership

Pass criteria:
1. Application services remain side-effect authority.
2. Adapters execute authorized effects but do not decide policy.
3. Decision nodes do not perform durable side effects.

Evidence:
1. Call-flow trace from interface -> application -> adapter/tool for affected operations.

### AC-06 Adapter Side-Effect Classification

Pass criteria:
1. New/changed adapters clearly declare side-effecting behavior.
2. Decision-node callers only consume side-effect-free adapter behavior.

Evidence:
1. Adapter contract/type declarations and caller review.

### AC-07 Runtime Truth Claims

Pass criteria:
1. Logs/events/user-facing messages do not claim success before verified state effect.
2. Advisory outcomes are explicitly labeled advisory.

Evidence:
1. Tests or run artifacts showing claim-after-verify sequencing.

### AC-08 Observability Schema Authority

Pass criteria:
1. Current runtime event fields remain aligned with `docs/architecture/event_taxonomy.md`.
2. Any schema evolution is versioned and documented; no silent dual authority.

Evidence:
1. Event payload diffs and associated docs update in same change.

### AC-09 Replayability Evidence

Pass criteria:
1. Critical changed operations emit replay-relevant artifacts or references.
2. Replay path for changed behavior is non-mutating and contract-aligned.

Evidence:
1. Integration/contract test output or artifact traces.

### AC-10 Authority Drift Control

Pass criteria:
1. If a change affects authoritative runtime behavior, corresponding docs/contracts are updated in the same change.
2. No silent drift between code, tests, and docs.

Evidence:
1. Updated authority docs where needed (`CURRENT_AUTHORITY.md`, specs, runbook, architecture docs).

## Suggested CI Gate Order

1. `AC-01`, `AC-04`, `AC-07` (high-value drift blockers)
2. `AC-02`, `AC-05`, `AC-08` (boundary integrity)
3. `AC-03`, `AC-06`, `AC-09`, `AC-10` (hardening completeness)
