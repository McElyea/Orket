# Orket Brainstorm — Runtime, OS, Extensions, Graphs, and Repo Anti-Patterns

Last updated: 2026-03-31  
Status: Brainstorm / strategic inventory grounded in current repo state  
Scope: What Orket can become, what it still needs, what is easiest to adopt next, and which anti-patterns are currently holding it back

## 1. Executive framing

The strongest coherent identity visible in the repo is not “generic agent framework.”

It is:

**Orket = governed capability runtime**  
that can evolve into a  
**supervisor / capability OS**  
that later supports  
**installable extensions, operator products, and specialized workloads**

That direction fits the repo’s strongest existing truths:

- canonical runtime and authority surfaces already exist
- governed turn-tool execution is real
- control-plane persistence exists for selected slices
- evidence surfaces and replay-oriented truth are already first-class
- graph work now has a truthful checkpointed home
- Companion work already established the correct thin-client / host-authority model

The highest-value move is not “add more agent vibes.”  
It is to finish the **runtime spine** so every future product sits on one execution, policy, evidence, and recovery story.

## 2. Repo-grounded current state

From the dump, the current repo already has the following important realities:

### 2.1 Operational authority is narrow and explicit

- `README.md` is intentionally narrow and points to `CURRENT_AUTHORITY.md` for exact runtime truth.
- `docs/ROADMAP.md` currently says the repo is in a **maintenance-only posture** with no active non-recurring lane open.
- `CURRENT_AUTHORITY.md` holds the real authority story for entrypoints, current control-plane seams, and active runtime truth.
- `docs/ARCHITECTURE.md` explicitly says the target architecture is still **transitioning** and lists known current exceptions.

### 2.2 Runtime truth is real, but not universal yet

The repo is already honest that some runtime properties are only partially universal:

- control-plane authority is **not universal** across all surfaces
- effect-journal publication is **not yet the default truth path**
- safe-tooling / namespace enforcement is strongest on the governed path
- supervisor-owned checkpointing is still partial

### 2.3 Graphs are real, but checkpointed

The graph family is no longer speculative. The repo now has:

- a shipped `RUN_EVIDENCE_GRAPH_V1` contract
- a non-archive Graphs checkpoint authority under `docs/projects/Graphs/`
- explicit acceptance that `authority` and `decision` remain filtered-view vocabulary over the existing semantic core
- explicit deferral of `workload-composition` and `counterfactual/comparison`

### 2.4 Companion already exposed the right product rule

The archived Companion gap packet made one key decision that still looks correct:

- **product-significant runtime authority belongs in the host**
- the external Companion repo should be a **thin client**
- frontend code must not become a second hidden authority center

That same rule should govern all future products and extensions.

## 3. North-star identity

A clean north-star statement for the repo is:

> Orket is a governed capability runtime where humans, models, schedulers, and rules can invoke the same capabilities under one control plane, one policy model, and one evidence trail.

A slightly more ambitious OS framing is:

> Orket becomes a supervisor OS for AI-era work: a system that admits, schedules, records, gates, resumes, and audits capability execution across multiple decision engines.

## 4. What Orket should do as a runtime

This is the runtime laundry list.

### 4.1 Finish universal workload authority

Natural next work:

- make one workload-authority seam universal across runtime admission paths
- stop letting side paths mint workload identity ad hoc
- keep public compatibility wrappers thin and routing-only
- remove any residual local workload-id/workload-version authority creation from runtime callsites

### 4.2 Finish universal safe tooling

Natural next work:

- extend governed turn-tool protections beyond the strongest governed path
- standardize capability grants, namespace scope, timeout rules, and tool result contracts
- make “unsafe path” impossible by default rather than documented as debt
- add explicit approval requirements for dangerous capability classes

### 4.3 Make effect truth universal

Natural next work:

- make effect journal / durable effect recording the default truth path
- stop projection-only surfaces from being the easiest or most convenient path to runtime truth
- require effect authority before reuse, replay, or claimed success
- unify tool/result/effect identity across runtime and recovery surfaces

### 4.4 Make checkpointing first-class

Natural next work:

- checkpoint / resume / replay / fork
- explicit “same attempt” vs “new attempt” semantics
- pause on approval and resume without replaying earlier work
- operator-visible checkpoint inventory
- deterministic pre-effect recovery and explicit reconciliation after uncertain boundaries

### 4.5 Add sessions as a real runtime concept

Natural next work:

- session identity separate from invocation identity
- session memory vs profile memory vs workspace memory split
- session-scoped context providers
- session replay / lineage / summary view
- session resource ownership and cleanup semantics

### 4.6 Add orchestration patterns as named runtime forms

Instead of bespoke loop logic everywhere, Orket should offer named patterns:

- direct action
- sequential pipeline
- orchestrator-worker
- maker-checker
- handoff
- approval-gated execution
- scheduler-triggered run
- event-triggered run

### 4.7 Add declarative workload specs

Natural next work:

- YAML / JSON workload definitions
- validation before run admission
- capability binding, approval requirements, timeouts, resource limits, and artifact contracts declared up front
- compiled workload graph / execution plan artifact

### 4.8 Add workflow composition

Natural next work:

- workflow-as-tool
- workflow-as-agent
- nested workloads with explicit parent-child lineage
- child capability contracts
- bounded recursion / cycle rules

### 4.9 Add a context-provider pipeline

Natural next work:

- memory provider
- retrieval provider
- policy/provider
- tool/provider
- operator context provider
- dynamic prompt/context injection through explicit providers instead of hand-built runtime glue

### 4.10 Add a stable live event stream

Natural next work:

- run started
- admission decision
- approval requested
- checkpoint written
- tool call requested
- tool call completed
- artifact written
- degraded / repaired / blocked state surfaced explicitly
- terminal summary emitted

## 5. What Orket should become as an OS

This is the “capability OS” / “supervisor OS” layer.

### 5.1 Principal model

Orket should treat these as first-class principals:

- model principal
- human operator principal
- scheduler principal
- rule-engine principal
- external service principal
- extension principal

### 5.2 Capability kernel

Everything durable or privileged should be expressed as a capability:

- read file
- write file
- query memory
- call browser
- send notification
- mutate workspace
- create artifact
- invoke external API
- perform OCR
- run evaluator
- request approval

Each capability should carry:

- determinism class
- risk level
- allowed callers
- resource scope
- timeout budget
- approval policy
- audit requirements

### 5.3 Process / run table

The runtime should expose a true run table:

- queued
- admitted
- blocked
- awaiting approval
- active
- recovering
- reconciliation-required
- terminal
- degraded
- repaired

### 5.4 Scheduler

Eventually Orket should support:

- cron
- event trigger
- dependency trigger
- policy trigger
- backoff
- max retry policy
- hold / resume / cancel
- budget-aware admission

### 5.5 Resource and lease model

The repo already has strong lifecycle/lease instincts in parts of the control plane. That should become universal:

- resource identity
- owner principal
- owner run/session
- lease epoch
- lease expiration
- reconciliation state
- cleanup ownership
- orphan detection

### 5.6 Namespace / tenancy

Orket as an OS should support at least:

- project namespace
- workload namespace
- extension namespace
- operator namespace
- workspace namespace
- resource namespace

### 5.7 Policy engine

A real OS posture needs:

- who may call what
- where it may run
- what requires approval
- what data can cross boundaries
- what side effects are allowed
- what models may be used for which job
- budget / quota / timeout rules

### 5.8 Package / extension manager

An OS posture eventually needs:

- install
- validate
- enable / disable
- version pin
- capability declaration
- permission manifest
- proof status
- compatibility status
- rollback

### 5.9 Operator shell / supervisor UI

Natural OS operator surfaces:

- inspect active runs
- inspect approvals
- inspect checkpoints
- inspect resources and leases
- replay or fork a run
- diff two runs
- audit capability usage
- inspect extension manifests
- inspect failure clusters

## 6. What Orket could support as extensions or products

These are the most natural product / extension directions visible from the repo and your ideation history.

### 6.1 Companion

Best posture:

- thin client
- host-owned orchestration
- host-owned memory retrieval
- host-owned session state
- host-owned generation pipeline
- extension entrypoints only for installability and capability registration

### 6.2 Voice Companion

Natural feature list:

- STT
- TTS
- silence and interruption handling
- turn timing and VAD policy
- persona / mode switching
- session memory
- profile memory
- multimodal responses
- avatar events only after host authority is stable

### 6.3 Local Tool Lab

A very natural near-term Orket product:

- let local models use tools safely
- compare model behavior under the same capability surface
- record failures truthfully
- run bounded tool-use experiments
- inspect policy violations and degraded outcomes

### 6.4 Code / repo operator

Natural feature list:

- repo analysis
- bounded code edits
- PR review
- test / fix loops
- release evidence generation
- proof packet assembly
- contract drift detection

### 6.5 Infrastructure reviewer

Natural feature list:

- deterministic first-pass analysis
- model-assisted explanation
- publish / no-publish decision
- operator-safe review mode
- proof and audit artifact output

### 6.6 UI Forge

Natural feature list:

- interface contract ingestion
- structured UI plan
- generated implementation workload
- proof that produced UI matches declared contract
- future workflow-as-tool composition with code/review operators

### 6.7 WorldBuilder / FinalJourney

Natural feature list:

- ingest media folder
- extract entities / environments / props / style
- preview inferred world
- compile world artifact
- later generate scenes against compiled world state
- treat the world artifact like a queryable runtime model

### 6.8 DND Survivors

Natural feature list:

- multi-agent role composition
- long-running bounded simulation
- environment ladder
- survival / competence scoring
- generational evaluation
- compare different model role assignments under the same runtime constraints

### 6.9 Incident investigator

Natural feature list:

- read-only log access
- summarize failures
- suggest next steps
- store investigation artifact
- explicitly forbid operational side effects

## 7. Graph roadmap

Given current repo posture, the safest graph order is:

### 7.1 Promote next

- authority graph
- decision graph

These are easiest because the repo already treats them as filtered-view vocabulary over the current semantic graph core.

### 7.2 Promote after that

- resource-authority graph
- closure graph

These fit your existing control-plane and evidence instincts.

### 7.3 Defer until explicit contract work

- workload-composition graph
- counterfactual/comparison graph

Both require tighter lineage, comparison-basis, and truthful path labeling before they should be promoted.

### 7.4 Additional graph ideas that fit Orket

- run timeline graph
- checkpoint lineage graph
- approval graph
- capability invocation graph
- resource lifecycle graph
- session lineage graph
- replay/fork graph
- degraded/repaired provenance graph
- extension dependency graph

## 8. Missing prerequisites before the bigger OS move

These are the things the repo most likely still needs before it can claim a stronger OS posture.

### 8.1 Runtime prerequisites

- universal workload admission path
- universal capability authorization path
- effect truth as default
- checkpoint inventory and recovery model
- stable run/session identifiers across all surfaces
- stable live event stream

### 8.2 Product prerequisites

- external extension packaging story that feels final
- stable SDK boundary
- extension validation and publish workflow
- capability registry surface that product code can rely on
- explicit memory split
- host API seam that product clients can trust

### 8.3 Operator prerequisites

- approval inbox
- recovery dashboard
- run diff / compare view
- graph explorer
- resource / lease inspector
- policy inspector
- extension install / validate / disable surface

## 9. Easy adoptions from the outside world

These are the external ideas that look easiest to borrow without becoming derivative.

### 9.1 Adopt soon

- checkpoint + interrupt + resume
- human approval gates
- named orchestration patterns
- workflow-as-tool composition
- declarative workflow definitions
- stable runtime event streaming
- MCP at the external tool boundary
- session + context provider pipeline
- middleware / interception stack for cross-cutting controls

### 9.2 Adopt carefully

- convenience “easy mode” builders for common workload patterns
- agent abstraction only as a thin layer over real capability / workflow primitives
- richer multi-agent patterns only after single-agent-with-tools and orchestrator-worker are boring and reliable

### 9.3 Do not copy

- vague “agent” terminology where capability or workload is the real unit
- hidden in-memory truth
- chatty multi-agent loops as a default execution model
- magic wrappers that bypass policy, capability, or evidence rules
- convenience APIs that silently create new authority centers

## 10. Repo anti-patterns observed in the dump

This section is intentionally blunt.

These are not all fatal, but they are the most obvious shapes that keep showing up.

### 10.1 Monolithic coordinator files

The clearest code smell is still the presence of very large coordinator modules at core runtime seams, for example:

- `orket/application/workflows/orchestrator_ops.py`
- `orket/runtime/execution_pipeline.py`
- `orket/interfaces/api.py`
- `orket/orchestration/engine.py`

These files are not just large. They sit on hot authority paths, which means size amplifies risk:

- harder to reason about invariants
- easier to hide compatibility debt
- more likely to mix orchestration, policy, recovery, and IO concerns
- harder to test by behavior boundary instead of implementation detail

### 10.2 Transitional wrapper debt is still visible

The repo is already honest that the canonical public runtime surface is `run_card(...)`, while `run_issue(...)`, `run_epic(...)`, `run_rock(...)`, and the CLI `--rock` alias survive as compatibility wrappers.

That is better than hidden duplication, but it is still debt.

Why it matters:

- it preserves old mental models
- it increases entrypoint surface area
- it lets historical naming survive inside current authority seams
- it makes “what is the real surface?” harder than it should be

### 10.3 Delegation-by-magic still exists on at least one core workflow seam

`orket/application/workflows/turn_executor.py` still uses `__getattr__` to build a delegated method map dynamically.

That pattern is dangerous on authority-critical paths because it:

- hides the true public/internal surface
- makes code search and refactoring less reliable
- weakens type and interface clarity
- encourages “just add another delegated helper” growth

Even when it works, it reads like a way to avoid choosing a real boundary.

### 10.4 The architecture still admits known exception zones

`docs/ARCHITECTURE.md` explicitly documents current transition debt, including:

- layering exceptions
- decision-node purity exceptions
- deterministic clock/input exceptions

This honesty is good.  
But the anti-pattern is that some of the repo’s most important rules are still partially “true in docs, partially violated in implementation.”

That creates a recurring risk:

- architecture reads cleaner than runtime
- enforcement is partly social instead of fully structural
- future work must keep checking exception lists instead of trusting the layer model

### 10.5 Documentation authority is stronger than package/product consolidation

The repo has a very strong authority/governance system, but the package and product surface still looks comparatively transitional.

Repo-level shape from the dump:

- `docs/` is enormous
- most docs under `docs/` are archived
- there are many contract delta / closeout / plan artifacts
- the runtime and SDK packaging story is smaller and thinner than the governance surface surrounding it

That is not a documentation problem by itself.  
The anti-pattern is **control-plane and governance accretion outrunning package simplification**.

Symptoms:

- lots of truth about the runtime
- fewer obvious “boring stable” installable product/app surfaces
- many closed lanes still shaping how the repo must be understood
- the repo can feel like a governance machine wrapped around a runtime instead of the other way around

### 10.6 Identity drift across surfaces

Different files still describe Orket in different ways:

- `pyproject.toml`: “Local-first multi-agent LLM automation platform”
- `README.md`: local-first workflow runtime for card-based execution, persistent state, tool gating, and multiple operator surfaces
- broader docs: deterministic runtime / governed capability framing

This is not catastrophic, but it matters.

It suggests the conceptual center is still shifting between:

- multi-agent platform
- workflow runtime
- deterministic runtime
- control plane
- future OS

That drift makes ecosystem design harder because people build against the words you use.

### 10.7 Partial package split / monorepo transition signals

The repo already has:

- root Python package
- separate `orket_extension_sdk`
- monorepo package CI config
- a package template that points toward a stronger `packages/core` / `packages/sdk` split than the current tree actually uses

That suggests the repo knows where it may want to go, but is not fully there yet.

The anti-pattern is not “you have a monorepo.”  
It is **half-landed structural intent**.

That tends to create:

- ambiguous boundaries
- duplicated release expectations
- more CI/governance complexity than the final package layout justifies

### 10.8 Historical lane gravity

The repo has a very large archived project history. That is useful, but it creates gravity.

The anti-pattern is not archiving.  
It is when archived lanes remain mentally active because:

- current truths are scattered across closeouts, checkpoints, deltas, and authority files
- contributors need historical context to reason about current seams
- naming and authority decisions remain shaped by old lane language

A runtime should increasingly read as present-tense machinery, not a museum of how it got there.

## 11. Anti-patterns I would treat as highest priority

If forced to rank them:

1. monolithic coordinator files on hot authority paths  
2. non-universal workload / control-plane / effect truth seams  
3. magic delegation and compatibility-wrapper residue  
4. architecture exceptions that remain live in important modules  
5. governance/documentation accretion outrunning package/product simplification  
6. identity drift in how Orket describes itself

## 12. Best near-term sequence

A sane sequence from here:

### Phase A — finish the runtime spine

- universal workload-authority path
- universal safe-tooling / capability authorization
- effect truth as default
- checkpoint / interrupt / approval / resume
- stable live event stream

### Phase B — stabilize extension and product seams

- stable SDK contract
- external extension validation / publish flow
- host API seam
- memory split
- workflow-as-tool composition
- MCP bridge layer

### Phase C — expose operator OS surfaces

- supervisor dashboard
- run / checkpoint / approval / recovery views
- graph explorer
- policy / capability inspector
- extension manager

### Phase D — grow product lines

- Local Tool Lab
- Companion / Voice Companion
- Code / repo operator
- infra reviewer
- WorldBuilder / FinalJourney
- DND Survivors

## 13. Most useful one-sentence rule for future ideation

When brainstorming a new Orket feature, ask:

> Is this making the runtime spine more universal, or is it adding product surface on top of runtime debt?

If it is the second one, it probably belongs after more runtime consolidation.

## 14. Bottom line

The repo is already much closer to a **governed runtime / supervisor OS** than to a normal “agent framework.”

The most valuable future is not to imitate the broad market.  
It is to finish what your own repo already implies:

- one capability model
- one authority model
- one evidence model
- one recovery model
- many decision engines
- many installable products

That is the shape that could become both a serious runtime and a serious platform.
