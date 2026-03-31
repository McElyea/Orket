# Orket Brainstorm Inventory v2

Last updated: 2026-03-31
Status: Brainstorm only
Authority status: Not authority. Not roadmap-ready execution planning.
Purpose: Capture repo truth now, a north-star thesis, the strongest anti-patterns visible in the dump, and a small set of bounded reopen candidates.

## 1. Usage boundary

This document is intentionally not a current-authority file.

It should be read as:
- a repo-grounded brainstorm and strategy memo,
- a staging surface for future lane selection,
- a place to separate what is true now from what Orket could become.

It should not be read as:
- roadmap authority,
- execution authority,
- proof of conformance,
- a claim that every listed future direction is active work.

## 2. Repo truth now

### 2.1 Roadmap posture

As of `docs/ROADMAP.md` dated 2026-03-30, the repo is in a maintenance-only posture:

- `Priority Now` says no active non-recurring lane is open.
- `ControlPlane` is paused at a truthful checkpoint.
- `Graphs` is paused at a truthful checkpoint.
- `marshaller` is future-hold.

That means any future move in this document is a reopen candidate, not a live lane.

### 2.2 Graphs posture

Graphs are not an active implementation lane right now.

What is true now:
- the roadmap still names `docs/projects/Graphs/` as a paused-checkpoint project,
- `CURRENT_AUTHORITY.md` names the canonical run-evidence graph operator path,
- `docs/specs/RUN_EVIDENCE_GRAPH_V1.md` is the durable active contract for the shipped run-evidence graph family.

What is not true now:
- Graphs are not a currently open roadmap lane,
- the repo should not be described as having active Graphs execution work in flight.

### 2.3 Current authority surfaces

The dump shows a narrow current-authority story:

- `README.md` is intentionally narrow and points to `CURRENT_AUTHORITY.md`.
- `CURRENT_AUTHORITY.md` is the live authority surface for entrypoints and operator paths.
- `docs/ARCHITECTURE.md` is target-state architecture, but explicitly marked transitioning.
- `docs/ARCHITECTURE.md` also explicitly lists known current exceptions and accepted transition debt.

### 2.4 Runtime truth is partially universal, not yet universal

The repo already has real governed runtime truth. It also still admits partiality.

Strongly grounded examples from the dump:
- governed turn-tool execution has a deep and explicit control-plane path,
- run-evidence graph emission is real and operator-visible,
- control-plane refs and projection-vs-authority framing are being tightened in many runtime surfaces,
- architecture docs still admit known current exceptions,
- roadmap posture does not claim that universal convergence is complete.

The correct summary is:

`real runtime truth exists, but universal runtime convergence is not finished.`

### 2.5 Product-authority rule already visible in Companion materials

The dump contains a strong product rule that still looks right:

- host-owned orchestration stays in the host,
- Companion is a thin client over host APIs,
- no product-significant runtime authority should live in frontend code or Companion-side shims.

That same rule should govern future Orket products and extensions.

## 3. Strongest anti-patterns visible in the repo

This section is intentionally blunt.

### 3.1 Monolithic hot-path modules

Several core runtime surfaces are too large for comfort and signal concentrated orchestration debt:

- `orket/application/workflows/orchestrator_ops.py` - about 2619 lines in the dump
- `orket/runtime/execution_pipeline.py` - about 2087 lines
- `orket/interfaces/api.py` - about 1674 lines
- `orket/orchestration/engine.py` - about 533 lines

This does not prove those modules are bad. It does strongly suggest:
- too many responsibilities meet in a few places,
- changes can create broad blast radius,
- architectural intent is likely cleaner than the current execution seams.

### 3.2 Compatibility surfaces are still visible on the main path

The repo has clearly done cleanup work here, but the cleanup is not fully cold yet.

Evidence visible in the dump:
- the CLI still documents `--rock` as a legacy compatibility alias,
- authority text still discusses `run_card(...)` as canonical while `run_issue(...)`, `run_epic(...)`, and `run_rock(...)` survive as thin wrappers,
- there is still active governance language dedicated to preventing drift back onto wrapper surfaces.

Anti-pattern:

`retired nouns and compatibility routes still consume enough surface area that governance has to keep policing them.`

That is truthful transition debt, but it is still debt.

### 3.3 Magic delegation on a core execution seam

`orket/application/workflows/turn_executor.py` still contains a large `__getattr__` delegation map.

That is a smell on a critical seam because it:
- hides the true public shape of the object,
- weakens readability and discoverability,
- makes refactor safety worse,
- encourages a facade that is broader than it looks.

For a core execution path, explicit composition is healthier than magic dispatch.

### 3.4 Target-state architecture with explicit exceptions is honest, but still a smell

`docs/ARCHITECTURE.md` says the codebase partially implements the rules and explicitly lists known current exceptions.

That honesty is good.
The anti-pattern is not the document.
The anti-pattern is the repo still needing a standing target-state-vs-current-state exception table in core architecture.

In plain English:

`the architecture is clearer than the implementation boundary in some important areas.`

### 3.5 Identity drift across surfaces

The dump shows at least two different outward identity stories:

- `README.md`: local-first workflow runtime
- `pyproject.toml`: local-first multi-agent LLM automation platform

Those are not identical claims.
They pull the mental model in different directions.

A repo can survive that for a while, but long term it creates:
- design drift,
- naming churn,
- mismatched expectations for extension authors and operators.

### 3.6 Packaging and boundary intent outpaces the final package layout

The dump includes both:
- a real package split (`orket` and `orket_extension_sdk`) in `.ci/packages.json`, and
- a cleaner future-looking package template (`packages/core`, `packages/sdk`) in `.ci/packages.template.json`.

That is not inherently wrong.
It does show a familiar anti-pattern:

`the repo knows the shape it may want later, but the lived package surface is still transitional.`

### 3.7 Governance maturity can outrun simplification maturity

The repo is very strong on governance language, authority surfaces, closeouts, contract docs, and anti-drift rules.
That is a strength.

The risk is this anti-pattern:

`the control-plane and governance story becomes more precise faster than the execution and package seams become simple.`

If that happens for too long, the repo remains truthful but expensive to reason about.

## 4. North-star thesis

The cleanest identity I see is:

**Orket is a governed capability runtime.**

More ambitious version:

**Orket can become a supervisor OS for AI-era work, where humans, models, schedulers, and rules invoke the same capabilities under one control plane, one policy story, and one evidence trail.**

This is a better identity than generic agent framework for three reasons:
- it matches the repo's strongest current truth surfaces,
- it centers authority and recovery instead of agent theater,
- it leaves room for products and extensions without creating a second hidden authority center.

## 5. Laundry list: what Orket should do as a runtime

These are brainstorm targets, not active commitments.

### 5.1 Execution and authority

- universal workload authority across all start paths
- universal safe-tooling defaults, not just strongest governed path coverage
- explicit capability grants with namespace scope, timeout, and approval policy
- durable effect journal as the default truth path
- one run / attempt / step identity story across runtime, replay, and artifacts

### 5.2 Recovery and supervision

- checkpoint / resume / replay / fork as first-class runtime behavior
- operator-visible pause and approval gates
- same-attempt vs new-attempt semantics made explicit
- deterministic pre-effect recovery and explicit post-effect reconciliation
- operator-visible checkpoint inventory and run lineage

### 5.3 Sessions and context

- session identity separate from invocation identity
- session memory vs profile memory vs workspace memory split
- context-provider pipeline for memory, retrieval, policy, tools, and operator context
- session lineage, summary, and cleanup semantics

### 5.4 Orchestration patterns

- direct action
- sequential pipeline
- orchestrator-worker
- maker-checker
- handoff
- approval-gated execution
- scheduler-triggered run
- event-triggered run

### 5.5 Workflow definition and composition

- declarative workload specs
- validation before admission
- workflow-as-tool
- workflow-as-agent
- explicit parent-child lineage
- bounded recursion and cycle rules

### 5.6 Operator and client surfaces

- stable live event stream
- operator hold / resume / approve / reject surfaces
- run diff and replay inspection
- resource and lease inspection
- public control-plane API for runs, approvals, artifacts, and policy

## 6. Laundry list: what Orket could become as an OS

This is not an operating system in the Linux sense.
It is a capability OS or supervisor OS.

### 6.1 Principal model

Treat these as first-class principals:
- human operator
- model
- scheduler
- rule engine
- extension
- external service

### 6.2 Capability kernel

Every privileged action becomes a named capability with:
- determinism class
- risk level
- allowed callers
- resource scope
- timeout budget
- approval policy
- audit requirements

### 6.3 Process and scheduler model

- run table with admitted, blocked, awaiting approval, active, recovering, terminal states
- scheduler for cron, dependency, event, and policy-triggered runs
- leases and reservations for durable ownership
- namespace and tenancy boundaries

### 6.4 State and package services

- session and memory services
- workspace snapshot and rollback services
- extension package manager and validator
- policy engine
- resource registry
- audit and evidence service

## 7. Extensions and products that fit naturally

- Companion as thin client over host-owned runtime authority
- Voice Companion with STT, TTS, turn timing, and session memory
- Local Tool Lab for safe local-model tool use under Orket policy
- code and repo operator
- Terraform / infra reviewer
- UI Forge / interface compiler
- WorldBuilder / FinalJourney style world-state compiler
- DND Survivors style long-horizon simulation extension
- research / requirements / proof packet engine
- read-only incident investigator
- connector packs and tool packs

## 8. Easy adoptions from the current framework landscape

This section is about patterns to steal, not frameworks to mimic.

### 8.1 Strong borrow candidates

- interrupt / approve / resume flows
- checkpoint-backed replay and state forking
- named orchestration patterns instead of custom loop shapes everywhere
- session and context-provider pipelines
- declarative workflows with compile-time validation
- workflow-as-tool composition
- MCP as a standard outer tool boundary
- stable event streaming for UI and operator clients

### 8.2 What not to borrow

- agent chatter as default architecture
- hidden in-memory truth
- convenience abstractions that become shadow authority
- vague language that blurs capability, workload, tool, policy, and side effect

## 9. Graphs: how to think about them now

Graphs should be treated as a paused family, not a live lane.

### 9.1 What feels safe if reopened

If Graphs are explicitly reopened, the safest next graph-family moves look like:
- authority graph
- decision graph

Reason:
- they are easier to frame as filtered views over existing semantic/runtime truth,
- they do not require inventing a whole new lineage regime first.

### 9.2 What should stay parked until prerequisites exist

- workload-composition graph
- counterfactual or comparison graph
- anything that implies stronger parent-child lineage truth than the runtime already has

## 10. Small set of actual reopen candidates

This is the most roadmap-useful section.
These are intentionally compressed and bounded.

### Candidate 1: Universal safe-tooling plus approval-checkpoint runtime

Purpose:
- make safe tool use and human approval a default runtime shape rather than a strongest-path specialty.

In scope:
- approval-required capability classes
- interrupt / approve / reject / resume runtime behavior
- checkpoint inventory and replay boundary semantics
- policy and namespace enforcement on more than the currently strongest governed slice

Out of scope:
- full memory system
- extension marketplace
- broad workflow DSL work

Acceptance boundary:
- one explicit interrupt and approval contract exists,
- one stable checkpoint-backed resume path exists,
- touched tool-capability classes fail closed without required approval,
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

### Candidate 3: Graphs family reopen for authority and decision views only

Purpose:
- reopen Graphs narrowly without pretending the whole family is ready.

In scope:
- authority graph
- decision graph
- filtered-view framing over existing truth surfaces
- explicit operator story for why these graphs matter

Out of scope:
- counterfactual graphing
- composition graphing
- new parent-child lineage inventions

Acceptance boundary:
- two graph views have explicit contract docs,
- they read from existing durable truth rather than ad hoc scraping,
- roadmap and closeout language remain truthful about the family staying bounded.

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

## 11. Recommended order

If only one or two lanes are reopened soon, the strongest order looks like:

1. Universal safe-tooling plus approval-checkpoint runtime
2. Sessions plus context-provider pipeline
3. Extension package / validate / publish hardening
4. Graphs family reopen for authority and decision views only

Reason:
- runtime supervision first,
- continuity second,
- extension surface third,
- more graph family work only after the underlying runtime seams are a little colder.

## 12. Closing judgment

Blunt version:

- As a brainstorm direction, Orket is strongest when it thinks of itself as a governed capability runtime.
- As an eventual platform, the natural expansion is toward a supervisor OS posture.
- As a repo today, the biggest risks are still monolithic orchestration seams, wrapper debt, identity drift, and governance complexity outrunning simplification.
- The next good move is not a huge roadmap explosion. It is picking one or two bounded reopen candidates and driving them to a cold checkpoint.
