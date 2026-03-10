# Architecture Compliance Checklist

Last updated: 2026-03-10  
Status: Active (transition-aware)

Use before merge for changes touching runtime, orchestration, adapters, interfaces, or decision nodes.

`docs/ARCHITECTURE.md` is target-state authority. Known Current Exceptions are transition debt and must not be widened.

## Usage

1. Record each check as `pass`, `partial`, or `fail`.
2. If `partial` or `fail`, include exact path(s) and reason.
3. If non-compliance is pre-existing, confirm the change did not widen it.
4. Scope review to behavior affected by the change. Unrelated legacy violations are not new failures unless expanded by the change.
5. For each `partial`, include a remediation path (explicit exception reference, active roadmap lane, or concrete follow-up owner + artifact).

## Checks

### AC-01 Dependency Direction
Pass criteria:
1. No new dependency edges violate allowed flow:
   1. `interfaces -> application`
   2. `application -> core/adapters/decision_nodes`
   3. `adapters -> core`
   4. `decision_nodes -> core contracts`
2. Dependency direction is not bypassed through dynamic imports or runtime reflection.

Evidence:
1. Import diff review for touched files and newly introduced reachable dependency surfaces.
2. Dependency-check output, if available.

### AC-02 Decision Node Purity
Pass criteria:
1. New/changed decision nodes do not add side effects.
2. No direct file/database/tool/external mutation from decision nodes.
3. No hidden cross-invocation mutable state.

Evidence:
1. Code diff shows structured input -> structured output behavior.
2. Tests cover observable decision contracts.

### AC-03 Explicit Input Contracts
Pass criteria:
1. Decision nodes receive required context through explicit structured inputs.
2. No runtime-context reach-through for decision semantics.

Evidence:
1. Contract signatures and application call sites.

### AC-04 Deterministic Runtime Inputs
Pass criteria:
1. New/changed deterministic runtime paths do not introduce nondeterministic identity or timing sources for deterministic decisions.
2. Time/randomness is passed explicitly through orchestrator inputs when required.

Evidence:
1. Code scan for `time.time()`, `datetime.now()`, `datetime.utcnow()`, `uuid4()`, `uuid.uuid4()`, `random.*`, `secrets.*`, `os.urandom()`, `numpy.random.*` in touched deterministic paths.

### AC-05 Side-Effect Ownership
Pass criteria:
1. Application services remain side-effect authority.
2. Adapters execute authorized effects but do not decide policy.
3. Decision nodes do not perform durable side effects.

Evidence:
1. Call-flow trace for affected operations: `interface -> application -> adapter/tool`.

### AC-06 Adapter Side-Effect Classification
Pass criteria:
1. New/changed adapters clearly declare side-effecting behavior.
2. Decision-node callers consume only side-effect-free adapter behavior.

Evidence:
1. Adapter contract/type declaration.
2. Caller review.

### AC-07 Runtime Truth Claims
Pass criteria:
1. Logs/events/user-visible messages do not claim success before verified state effect.
2. Advisory outcomes are labeled advisory.
3. Failure to verify state effect is not reported as success or success-shaped completion.

Evidence:
1. Tests or run artifacts showing claim-after-verify sequencing.
2. Negative-path evidence for affected operations.

### AC-08 Observability Schema Authority
Pass criteria:
1. Runtime event fields remain aligned with `docs/architecture/event_taxonomy.md`.
2. Schema evolution is versioned and documented.
3. No silent dual authority exists.

Evidence:
1. Event payload diff review.
2. Docs updates in the same change when schema changes occur.

### AC-09 Replayability Evidence
Pass criteria:
1. Critical changed operations emit replay-relevant artifacts or stable references.
2. Replay paths are non-mutating and contract-aligned.
3. Replay evidence is sufficient to reconstruct decision-relevant inputs.

Evidence:
1. Integration/contract test output or artifact traces.

### AC-10 Authority Drift Control
Pass criteria:
1. Changes affecting authoritative runtime behavior update corresponding docs/contracts in the same change.
2. No silent drift exists between code, contract tests, and docs.

Evidence:
1. Updated authority docs where required (for example `CURRENT_AUTHORITY.md`, `docs/ARCHITECTURE.md`, `docs/architecture/event_taxonomy.md`, impacted `docs/specs/*`, and `docs/RUNBOOK.md`).

## Suggested Check Order

1. AC-01, AC-04, AC-07
2. AC-02, AC-05, AC-08
3. AC-03, AC-06, AC-09, AC-10
