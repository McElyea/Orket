# Orket Brainstorm Inventory v4

Last updated: 2026-03-31
Status: Brainstorm only
Authority status: Not authority. Not roadmap-ready execution planning.
Purpose: Capture authority-backed repo posture, reviewed snapshot inputs, a north-star thesis, and a small set of bounded future-lane candidates.

## 1. Usage boundary

This document is intentionally not a current-authority file.

It should be read as:
- a brainstorm and strategy memo,
- a staging surface for future lane selection,
- a place to separate authority-backed current posture from future-facing ideas.

It should not be read as:
- roadmap authority,
- execution authority,
- proof of conformance,
- a claim that every listed future direction is active work.

## 2. Repo truth now

### 2.1 Authority-backed posture only

The only repo-posture claim this memo relies on is:

- the roadmap is currently in a maintenance-only posture,
- no active non-recurring lane is open.

That means every future move listed here is a candidate for explicit reopening or future selection, not live execution authority.

### 2.2 What this memo deliberately does not claim

Because earlier drafts drifted on Graphs posture, this memo does not use Graphs status as a required present-tense premise for the rest of the document.

This memo does not require the reader to accept any future direction merely because Graphs or another paused family exists in non-active project form.

Graphs remain useful here only as a conditional future topic:
- if Graphs are explicitly reopened later, this memo suggests a narrow shape for that reopen.

### 2.3 Current-authority surfaces

The current repo posture should be read from authority-backed surfaces, not from this memo.

This memo assumes the following rule:
- roadmap posture comes from `docs/ROADMAP.md`,
- canonical runtime/operator entrypoints come from `CURRENT_AUTHORITY.md`,
- brainstorm material under `docs/projects/future/brainstorm/` must not override either one.

## 3. Reviewed inputs for snapshot observations

Sections 4 through 10 use reviewed snapshot inputs rather than current-authority claims.

Reviewed inputs for those sections:
- `docs/ROADMAP.md`
- `README.md`
- `pyproject.toml`
- `docs/ARCHITECTURE.md`
- `orket/application/workflows/turn_executor.py`
- `docs/projects/archive/Companion/CP03092026-MVP-CLOSEOUT/00-GAP-SUMMARY-AND-DEPENDENCY-MAP.md`
- `docs/projects/archive/Companion/CP03092026-MVP-CLOSEOUT/01-COMPANION-EXTERNAL-EXTENSION-PLAN.md`
- `docs/projects/archive/Companion/CP03092026-MVP-CLOSEOUT/04-MEMORY-SUBSYSTEM-SPLIT.md`
- `docs/projects/archive/Companion/CP03092026-MVP-CLOSEOUT/05-VOICE-STT-TURN-CONTROL.md`

The rule for this memo is:
- if a statement is meant as current posture, it belongs in Section 2 and must be safe under current authority,
- if a statement depends on these reviewed files, it is a snapshot observation only.

## 4. Snapshot observations that still matter

These are not authority claims.
They are planning observations from reviewed repo materials.

### 4.1 Runtime truth is real, but convergence is still incomplete

Observed pattern:
- the repo contains real governed runtime and evidence surfaces,
- architecture materials still acknowledge current exceptions or transition debt,
- the roadmap posture does not claim that universal convergence is finished.

Useful planning conclusion:
- Orket already behaves more like a governed runtime than a generic agent playground,
- but "universal runtime convergence is complete" would still be an overclaim.

### 4.2 Product-significant authority should stay in the host

Observed pattern:
- the archived Companion gap and plan materials are explicit that backend logic, memory retrieval, generation orchestration, and session state belong in the host,
- those same materials explicitly define the Companion repo as a thin client rather than a second runtime authority center.

Useful planning conclusion:
- future products and extensions should keep runtime authority in the host and treat client-facing repos as thin presentation and integration surfaces.

## 5. Strongest anti-patterns visible in reviewed repo materials

Each item below is tagged as either:
- **lane-seed**: can plausibly become a bounded future lane candidate,
- **thesis-only**: useful diagnosis, but not clean enough by itself to become a lane.

### 5.1 Monolithic hot-path modules  [lane-seed]

Several core runtime surfaces are large enough to signal concentrated orchestration debt:

- `orket/application/workflows/orchestrator_ops.py`
- `orket/runtime/execution_pipeline.py`
- `orket/interfaces/api.py`
- `orket/orchestration/engine.py`

Why it matters:
- too many responsibilities meet in a few places,
- change blast radius is harder to contain,
- target-state architecture is likely cleaner than the current hot-path seams.

Closest bounded lane direction:
- runtime seam extraction and supervision-boundary hardening.

### 5.2 Compatibility-wrapper debt  [lane-seed]

Reviewed materials still showed compatibility or retired-noun surfaces living near the canonical path.

Why it matters:
- wrapper surfaces keep old names alive,
- governance must keep policing drift back onto transitional routes,
- the public surface stays broader than it really wants to be.

Closest bounded lane direction:
- canonical runtime surface cold-down and wrapper retirement.

### 5.3 Magic delegation on a core execution seam  [lane-seed]

`orket/application/workflows/turn_executor.py` contains `__getattr__` delegation on a critical seam.

Why it matters:
- the true public shape is harder to read,
- refactor safety is weaker,
- composition boundaries are less explicit than they should be.

Closest bounded lane direction:
- explicit execution-surface composition and facade reduction.

### 5.4 Target-state architecture still needs exception tables  [lane-seed]

`docs/ARCHITECTURE.md` is honest about current exceptions and transition debt.

Why it matters:
- the problem is not the honesty,
- the problem is that important architecture rules still need a standing exception ledger.

Closest bounded lane direction:
- close one bounded exception family at a time until the standing exception table gets smaller.

### 5.5 Identity drift across surfaces  [lane-seed]

The reviewed snapshot shows more than one outward identity story for the repo.

Concrete example:
- `README.md` describes Orket as "a local-first workflow runtime for card-based execution with persistent state, tool gating, and multiple operator surfaces."
- `pyproject.toml` describes it as a "Local-first multi-agent LLM automation platform."

Why it matters:
- naming and expectations drift,
- extension authors and operators can optimize for different mental models,
- roadmap discussions become noisier than they need to be.

Closest bounded lane direction:
- repo identity and supported-surface alignment.

### 5.6 Transitional package/boundary intent  [lane-seed]

Reviewed materials show a real package split plus evidence of a cleaner future package shape.

Why it matters:
- the repo can know its desired package shape before it reaches it,
- but long transition windows keep package and authority seams harder to reason about.

Closest bounded lane direction:
- extension package / validate / publish hardening.

### 5.7 Governance precision can outrun simplification  [thesis-only unless decomposed]

The repo is strong on governance, closeouts, authority language, and anti-drift rules.

Why it matters:
- that strength can still become expensive if execution seams stay broad and transitional for too long.

Why this is not yet a clean lane by itself:
- it is a meta-diagnosis, not one bounded execution packet.

Correct use:
- treat this as a prioritization rule over other lanes, not as a standalone lane.

## 6. North-star thesis

The cleanest identity I see is:

**Orket is a governed capability runtime.**

More ambitious version:

**Orket can become a supervisor OS for AI-era work, where humans, models, schedulers, and rules invoke the same capabilities under one control plane, one policy story, and one evidence trail.**

This is a better identity than generic agent framework because:
- it matches the strongest runtime and authority instincts already visible in the repo,
- it centers policy, recovery, and truth instead of agent theater,
- it supports products and extensions without creating a second hidden authority center.

## 7. Laundry list: what Orket should do as a runtime

These are brainstorm targets, not active commitments.

### 7.1 Execution and authority

- universal workload authority across all start paths
- universal safe-tooling defaults, not just strongest-path coverage
- explicit capability grants with namespace scope, timeout, and approval policy
- durable effect journal as the default truth path
- one run / attempt / step identity story across runtime, replay, and artifacts

### 7.2 Recovery and supervision

- checkpoint / resume / replay / fork as first-class runtime behavior
- operator-visible pause and approval gates
- same-attempt vs new-attempt semantics made explicit
- deterministic pre-effect recovery and explicit post-effect reconciliation
- operator-visible checkpoint inventory and run lineage

### 7.3 Sessions and context

- session identity separate from invocation identity
- session memory vs profile memory vs workspace memory split
- context-provider pipeline for memory, retrieval, policy, tools, and operator context
- session lineage, summary, and cleanup semantics

### 7.4 Orchestration patterns

- direct action
- sequential pipeline
- orchestrator-worker
- maker-checker
- handoff
- approval-gated execution
- scheduler-triggered run
- event-triggered run

### 7.5 Workflow definition and composition

- declarative workload specs
- validation before admission
- workflow-as-tool
- workflow-as-agent
- explicit parent-child lineage
- bounded recursion and cycle rules

### 7.6 Operator and client surfaces

- stable live event stream
- operator hold / resume / approve / reject surfaces
- run diff and replay inspection
- resource and lease inspection
- public control-plane API for runs, approvals, artifacts, and policy

## 8. Laundry list: what Orket could become as an OS

This is not an operating system in the Linux sense.
It is a capability OS or supervisor OS.

### 8.1 Principal model

Treat these as first-class principals:
- human operator
- model
- scheduler
- rule engine
- extension
- external service

### 8.2 Capability kernel

Every privileged action becomes a named capability with:
- determinism class
- risk level
- allowed callers
- resource scope
- timeout budget
- approval policy
- audit requirements

### 8.3 Process and scheduler model

- run table with admitted, blocked, awaiting approval, active, recovering, terminal states
- scheduler for cron, dependency, event, and policy-triggered runs
- leases and reservations for durable ownership
- namespace and tenancy boundaries

### 8.4 State and package services

- session and memory services
- workspace snapshot and rollback services
- extension package manager and validator
- policy engine
- resource registry
- audit and evidence service

## 9. Extensions and products that fit naturally

This list is useful only if it stays tied to the lane candidates below.

### 9.1 Directly aligned to Candidate 1 or Candidate 2

- Local Tool Lab for safe local-model tool use under Orket policy
- Companion as a thin client over host-owned runtime authority
- Voice Companion with STT, TTS, turn timing, and session memory

### 9.2 Directly aligned to Candidate 4

- connector packs and tool packs
- external extension repos with install / validate / publish support

### 9.3 Better treated as downstream consumers, not near-term lanes

- code and repo operator
- Terraform / infra reviewer
- UI Forge / interface compiler
- WorldBuilder / FinalJourney style world-state compiler
- DND Survivors style long-horizon simulation extension
- research / requirements / proof packet engine
- read-only incident investigator

## 10. Easy adoptions from the current framework landscape

This section is about patterns to steal, not frameworks to mimic.

### 10.1 Strong borrow candidates

- interrupt / approve / resume flows
- checkpoint-backed replay and state forking
- named orchestration patterns instead of custom loop shapes everywhere
- session and context-provider pipelines
- declarative workflows with compile-time validation
- workflow-as-tool composition
- MCP as a standard outer tool boundary
- stable event streaming for UI and operator clients

### 10.2 What not to borrow

- agent chatter as default architecture
- hidden in-memory truth
- convenience abstractions that become shadow authority
- vague language that blurs capability, workload, tool, policy, and side effect

## 11. Graphs: how to treat them in this memo

This memo treats Graphs only as a conditional future topic.

It does not assert that Graphs should reopen soon.
It does not treat the existence of paused Graphs material as a reason to promote graph-family work now.

If Graphs are ever explicitly reopened, the safest narrow reopen still looks like:
- authority graph
- decision graph

And the following should stay parked until stronger prerequisites exist:
- workload-composition graph
- counterfactual or comparison graph
- anything that assumes stronger parent-child lineage truth than the runtime already has

## 12. Small set of actual future-lane candidates

This is the most roadmap-useful section.
These are intentionally compressed and bounded.

### Candidate 1: Approval-checkpoint runtime slice

Purpose:
- make one approval-required runtime path fully explicit, interruptible, and resumable without pretending to solve all safe-tooling coverage at once.

In scope:
- one explicit approval-required capability class
- interrupt / approve / reject / resume runtime behavior for that class
- one stable checkpoint-backed resume path
- operator-visible approval and resume lineage

Out of scope:
- universal safe-tooling coverage
- full memory system
- extension marketplace
- broad workflow DSL work

Acceptance boundary:
- one explicit interrupt and approval contract exists,
- one stable checkpoint-backed resume path exists,
- the touched capability class fails closed without required approval,
- operator-visible evidence shows approval and resume lineage.

### Candidate 2: Sessions plus context-provider pipeline

Purpose:
- turn continuity into a runtime primitive instead of ad hoc glue.

In scope:
- session identity
- session memory vs profile memory vs workspace memory separation
- context-provider injection model
- session lineage and cleanup rules

Out of scope:
- broad social companion UX
- frontend product work
- broad knowledge/memory ranking ambitions

Acceptance boundary:
- one canonical session model exists,
- providers are explicit and pluggable,
- session replay and summary surfaces are operator-visible,
- the host remains the sole runtime authority.

### Candidate 3: Conditional Graphs reopen for authority and decision views only

Purpose:
- define the narrowest graph-family reopen worth considering if Graphs are ever explicitly reopened again.

Precondition:
- Graphs must be explicitly reopened by roadmap authority before any execution work is implied.

In scope after explicit reopen:
- authority graph
- decision graph
- filtered-view framing over existing durable truth surfaces
- explicit operator reason for why these graph views matter

Out of scope:
- counterfactual graphing
- composition graphing
- new parent-child lineage inventions

Acceptance boundary after explicit reopen:
- the reopen is explicit in roadmap authority,
- one canonical operator path exists for each admitted graph view,
- one proof path exists for each admitted graph view,
- both views read from existing durable truth rather than ad hoc scraping,
- closeout language remains truthful that the family stayed narrowly bounded.

### Candidate 4: Extension package / validate / publish hardening

Purpose:
- make extensions a real package surface instead of mostly a runtime-internal capability.

In scope:
- package/install/update contract
- validation CLI
- manifest validation and permission declarations
- versioning and compatibility rules
- operator-facing install and audit story

Out of scope:
- public marketplace
- cloud hosting platform
- broad monetization or distribution work

Acceptance boundary:
- extension install/validate/publish has one canonical operator path,
- permission and capability declarations are explicit,
- extension failure modes are governed and inspectable,
- extension authors do not need repo-internal knowledge to use the supported path.

## 13. Recommended order

If only one or two lanes are reopened soon, the strongest order looks like:

1. Approval-checkpoint runtime slice
2. Sessions plus context-provider pipeline
3. Extension package / validate / publish hardening
4. Conditional Graphs reopen for authority and decision views only

Reason:
- runtime supervision first,
- continuity second,
- extension surface third,
- graph-family work only after underlying runtime seams are colder and only if explicit reopen authority exists.

## 14. Closing judgment

Blunt version:

- As a brainstorm direction, Orket is strongest when it thinks of itself as a governed capability runtime.
- As an eventual platform, the natural expansion is toward a supervisor OS posture.
- As a reviewed code-and-doc snapshot, the biggest visible risks are still monolithic orchestration seams, wrapper debt, identity drift, and transition complexity.
- The next good move is not a huge roadmap explosion. It is picking one or two bounded future-lane candidates and driving them to a cold checkpoint.
