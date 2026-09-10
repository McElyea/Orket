# Architectural Truth Remediation Plan

Date: 2026-07-29
Last updated: 2026-09-07
Status: Active implementation plan
Roadmap state: Priority Now
Inputs:

1. `docs/projects/future/BRUTAL_CODE_REVIEW_ARCHITECTURAL_TRUTH_2026-07-29.md`
2. `docs/projects/future/BEHAVIORAL_REVIEW_ARCHITECTURAL_TRUTH_2026-07-29.md`
3. `docs/architecture/CONTRACT_DELTA_ARCHITECTURAL_TRUTH_SLICE_A_2026-07-29.md`
4. `docs/architecture/CONTRACT_DELTA_ARCHITECTURAL_TRUTH_COMMAND_ROOT_2026-07-30.md`
5. `docs/architecture/CONTRACT_DELTA_ARCHITECTURAL_TRUTH_API_INSTANCES_B1_2026-07-30.md`
6. `docs/architecture/CONTRACT_DELTA_ARCHITECTURAL_TRUTH_API_COMPOSITION_B2_2026-09-07.md`

## Objective

Make Orket's executable behavior, dependency graph, tests, authority documents, and operator entrypoints tell the same architectural truth.

This plan does not aim to make the entire repository match the target architecture in one refactor. It establishes trustworthy gates, repairs the highest-risk behavior, and then removes transitional authority in bounded slices.

## Activation rule

The user explicitly activated this plan for implementation on 2026-07-29.

Activation state:

1. user implementation authority: accepted;
2. initial contract delta: recorded;
3. roadmap lane: active;
4. canonical plan: moved into `docs/projects/architectural-truth/`;
5. Workstream 0 baseline: implemented and rerunnable at
   `docs/projects/architectural-truth/architectural_truth_baseline.json`.

## Source-wrapper removal tracking

Core 0.6.0 retains the existing wrapper and hidden alias through 0.6.x.
Remove them only with an explicit 0.7.0 delta and installed-root proof.
Authority: `docs/architecture/CONTRACT_DELTA_GOVERNED_AGENT_RELEASE_2026-09-10.md`.

## Current execution state

Completed slices: Slice A -- Failure must fail; Slice B -- Real API instances.
Active slice: Slice C -- Architecture gate cutover.

Slice B is implemented. B1 established distinct factory-created app identity,
runtime graphs, request context, and teardown. B2 removed the module-default
compatibility owner and aliases, moved outward store/service and model-selector
composition into the application-owned container factory, and removed
`AT-EX-002` after import-purity, distinct-owner, concurrency, and teardown proof.

Current order:

1. ratify the current-layer mapping for Slice C;
2. implement allowed-edge enforcement from that one authority;
3. convert every retained violation to an exact governed exception without
   weakening the gate.

Implemented in Slice A:

1. `run_cli()` now returns explicit integer outcomes and `main.py` propagates failures;
2. synchronous first-run setup runs outside the active event loop;
3. first-run narration follows successful settings persistence;
4. `orket-quickstart` has help, scripted decisions, workspace selection, and structured EOF refusal;
5. the governed-run default scenario is installed package data;
6. native subprocess and outside-checkout behavioral tests cover the repaired paths;
7. `orket runtime` is the canonical installed default runtime;
8. `orket runtime --card <card_id>` forwards into the existing card parser;
9. `python main.py [runtime arguments]` is explicitly bounded compatibility through
   `0.6.x`, with removal requiring an explicit `0.7.0` contract delta;
10. `main.py` delegates to the installed composition root instead of duplicating
    bootstrap, exception logging, or exit-code mapping.

Implemented in Slice B1:

1. `create_api_app()` returns a new FastAPI object on every call;
2. each created app owns a distinct runtime container, root, decision node,
   runtime state, runtime host, engine, outbound-policy snapshot, and lazy
   stream/interaction/extension owners;
3. HTTP, websocket, and lifespan code resolve ownership through the active ASGI app;
4. tracked tasks and the app-owned engine are closed idempotently at teardown;
5. module-default aliases are confined to the compatibility default app;
6. concurrent-request, one-app-close, and repeated-lifecycle integration proof is
   implemented in `tests/interfaces/test_api_composition_isolation.py`.

Implemented in Slice B2:

1. importing `orket.interfaces.api` creates no FastAPI app, engine, state,
   decision node, stream, interaction, extension, or other runtime owner;
2. module-default `app` and mutable compatibility aliases are removed;
3. `orket/application/services/api_runtime_composition.py` constructs the full
   per-app graph, including outward stores/services and model-selection factory;
4. interface routes retrieve already-owned dependencies from the active app
   context and construct no protected-layer implementation class;
5. API tests patch explicit app containers and production startup retains the
   factory result;
6. distinct stores, event queues, extension catalogs, concurrent roots,
   isolated close, and repeated teardown are integration/contract proven.

Carried after Slice B2:

1. broader transport/facade extraction remains under `AT-EX-003`;
2. package-only `orket/` Ruff inventory remains red at the latest measured count;
3. repository-root Ruff inventory remains red at the latest measured count;
4. remaining registered exceptions stay assigned to their owning workstreams;
5. the workspace-local installed-wheel proof directory remains because execution
   policy rejected recursive cleanup after containment verification.

Completed proof checkpoints:

1. Workstream 0 baseline is rerunnable at
   `docs/projects/architectural-truth/architectural_truth_baseline.json`;
2. current exceptions have owner, reason, evidence, status, and removal condition in
   `docs/projects/architectural-truth/ARCHITECTURE_EXCEPTION_REGISTER.json`;
3. the former API same-object characterization is replaced by real isolation,
   concurrency, compatibility-scope, and teardown tests;
4. `/health` was already documented as unauthenticated minimal liveness in
   `docs/API_FRONTEND_CONTRACT.md`;
5. built-wheel proof covered all installed help surfaces plus the quickstart and governed-run defaults outside the checkout;
6. the exact canonical pytest command passes;
7. changed-file Ruff and documentation/governance checks pass;
8. the installed `orket.cli:main` root, runtime help, fresh setup, handled fatal,
   and invalid-card paths pass outside the checkout;
9. command-root proof is recorded in
   `docs/projects/architectural-truth/COMMAND_ROOT_PROOF_2026-07-30.md`;
10. package-only and repository-root Ruff counts remain truthfully red and distinct;
11. API B1 isolation and teardown proof is recorded in
    `docs/projects/architectural-truth/API_INSTANCE_B1_PROOF_2026-07-30.md`.

## Non-goals

1. A repo-wide namespace rename.
2. Moving files solely to make the package tree resemble the diagram.
3. Adding compatibility shims without explicit approval and a removal ticket.
4. Treating passing unit or structural tests as live entrypoint proof.
5. Decomposing large files before their authority boundaries are decided.
6. Rewriting control-plane contracts that already have truthful durable authority unless a contract delta is necessary.

## Governing principles

1. Fix false success before adding features.
2. Fix proof semantics before using proof output to prioritize refactors.
3. Prefer allowlisted dependency direction over incomplete denylists.
4. Keep one composition root per runtime surface.
5. Keep core pure; move effects outward.
6. Make compatibility debt explicit, expiring, and measurable.
7. Preserve bounded governed-action and governed-run behavior while changing composition.

## Workstream 0 — Freeze false claims and record the baseline

Priority: P0
Purpose: Prevent more code from depending on known lies.

### Required changes

1. Add a baseline report containing:
   - the current dependency edge matrix;
   - current architecture exceptions;
   - canonical command exit behavior;
   - API singleton behavior;
   - taxonomy, lint, file-size, function-size, and no-op results.
2. Mark the current API same-object behavior as a legacy singleton characterization, not isolation proof.
3. Label `/health` as liveness-only in its durable API contract.
4. Add a temporary release blocker for false-success CLI exits.
5. Do not add new imports to `orket/interfaces/api.py`, new core effects, new process-global runtime owners, or new environment reads in decision nodes.

### Acceptance gates

1. Baseline artifact is stable and rerunnable.
2. Every exception has an owner, reason, and removal condition.
3. No new violations are introduced between baseline and first remediation commit.

## Workstream 1 — Repair canonical command and exit-code truth

Priority: P0
Depends on: Workstream 0

### Required changes

1. Change the CLI application boundary to return a typed result with an exit code or raise typed failures.
2. Keep exception logging and exit-code mapping at one top-level boundary.
3. Make first-run onboarding async-safe.
4. Ensure success narration occurs after settings persistence is verified.
5. Add argument parsing and noninteractive behavior to `orket-quickstart`.
6. Package the governed-run default scenario as a package resource.
7. Choose and document one installed root command for the supported runtime.
8. Keep `main.py` and other source scripts as thin wrappers only during an explicitly approved compatibility window.

### Required tests

Classify these as end-to-end:

1. fresh install/fresh directory first run;
2. first-run persistence failure;
3. `--help` for every installed command;
4. quickstart approval, denial, invalid input, and EOF;
5. governed-run default demo from outside the checkout;
6. named card invalid target and startup configuration failure;
7. success and failure exit codes from native subprocesses.

### Acceptance gates

1. No fatal/error-shaped output exits `0`.
2. The default runtime is invocable from an installed package outside the checkout.
3. Default demo assets resolve without current-working-directory dependence.
4. First-run onboarding persists once and remains idempotent.

Checkpoint status: Complete on 2026-07-30. Live and structural proof is recorded
in `docs/projects/architectural-truth/COMMAND_ROOT_PROOF_2026-07-30.md`.

## Workstream 2 — Create real application composition roots

Priority: P0
Depends on: Workstream 1

### Required changes

1. Introduce an application-owned runtime container for:
   - engine;
   - persistence adapters;
   - decision-node registry;
   - extension runtime;
   - stream bus and interaction manager;
   - runtime state and background tasks.
2. Make `create_api_app()` create a new FastAPI object on every call.
3. Register routes and middleware against the new instance.
4. Store only instance-owned context on `app.state`.
5. Remove module-global owner adoption and eager engine creation.
6. Move outward pipeline store/service factories out of `orket/interfaces/api.py`.
7. Make lifespan teardown close engine, clients, background tasks, queues, and extension resources.
8. Make CLI and API composition reuse the same application factory where behavior overlaps.

### Required tests

Classify these as integration or end-to-end:

1. two simultaneous apps with distinct roots;
2. distinct engines, stores, event queues, settings, and extension catalogs;
3. concurrent request isolation;
4. one app closing without changing the other;
5. repeated construction with no orphaned owners;
6. module import with no mutable runtime construction.

### Acceptance gates

1. `create_api_app(A) is not create_api_app(B)`.
2. No application, adapter, decision-node, kernel, or orchestration implementation is constructed in a router module.
3. No mutable runtime owner remains module-global in `orket.interfaces.api`.
4. Live teardown proof observes zero leaked tasks/resources.

B1 checkpoint status: complete on 2026-07-30, with live and structural evidence in
`docs/projects/architectural-truth/API_INSTANCE_B1_PROOF_2026-07-30.md`. Gate 1
is implemented and live-proven. App identity, per-app owner graphs, concurrent
request resolution, one-app-close isolation, and tracked task/engine teardown are proven.

B2 checkpoint status: complete on 2026-09-07, with integration and structural
evidence in `docs/projects/architectural-truth/API_COMPOSITION_B2_PROOF_2026-09-07.md`.
All four Workstream 2 gates pass: the interface imports without owners, protected
implementation construction lives in the application composition root, per-app
stores/queues/catalogs are distinct, and repeated lifespan teardown leaves no
tracked task or open app-owned engine. `AT-EX-002` is removed. `AT-EX-003`
continues to track broader interface transport/facade extraction beyond this
API ownership workstream.

## Workstream 3 — Make dependency enforcement match the normative architecture

Priority: P0
Depends on: Workstream 2

### Required changes

1. Decide whether `runtime`, `orchestration`, `kernel`, `services`, `platform`, and other current classifications are:
   - application subdomains;
   - core subdomains;
   - adapters;
   - interfaces;
   - decision nodes;
   - temporary exceptions.
2. Record that mapping in one machine-readable architecture manifest.
3. Express allowed edges, not only forbidden pairs.
4. Fail on unexpected layers, edges, and authority-layer cycles.
5. Represent transitional exceptions as records with:
   - exact source and target;
   - owner;
   - reason;
   - introduced date;
   - removal trigger;
   - optional expiry release.
6. Generate architecture documentation and dependency reports from the same manifest.
7. Keep import graph output separate from pass/fail policy output.

### Acceptance gates

1. The checker fails on `core -> services`, `runtime -> interfaces`, and `interfaces -> adapters` unless an exact active exception exists.
2. The checker cannot be made green by inventing an ungoverned layer classification.
3. `docs/ARCHITECTURE.md`, its exception list, and the machine policy share one source.
4. CI publishes the observed graph and exception consumption.

## Workstream 4 — Restore core purity and explicit inputs

Priority: P1
Depends on: Workstream 3

### Required changes

1. Replace `FailureReporter.generate_report()` with:
   - a pure core failure-report value builder;
   - an application artifact writer;
   - an application observability publisher.
2. Move `ASTValidator` and `iDesignValidator` dependencies out of core policy or invert them behind core contracts.
3. Move reconciliation file traversal and logging out of core.
4. Inject clock, identity, and randomness values into core transitions.
5. Inventory core imports and effects mechanically.
6. Add pure deterministic tests for extracted core logic and integration tests for application effects.

### Acceptance gates

1. Core imports only standard library, approved schema libraries, and core modules.
2. No core module writes files/databases, emits logs/events, invokes tools, reads environment, or calls wall clock/randomness directly.
3. Repeated core calls with identical explicit inputs produce byte-equivalent serialized outputs where the contract claims determinism.

## Workstream 5 — Remove async event-loop blocking

Priority: P1
Depends on: Workstream 2

### Required changes

1. Build a reachability-aware inventory from async entrypoints.
2. Replace reachable:
   - `subprocess.run()`/`subprocess.call()`;
   - `Path.read_text()`/`write_text()`;
   - raw `open()`;
   - sync HTTP;
   - `time.sleep()`.
3. Convert extension installation and integrity checks to async execution or isolate them in a supervised worker.
4. Convert runtime-policy artifact reads to async or preloaded application snapshots.
5. Keep explicit exemptions only for standalone CLI/CI scripts.

### Required tests

1. event-loop responsiveness during settings reads;
2. cancellation and timeout of extension subprocesses;
3. concurrent API requests during artifact reads;
4. shutdown while subprocess or file work is active.

### Acceptance gates

1. Static async-safety gate passes with no unexplained exemptions.
2. Live responsiveness tests meet a documented latency bound.
3. Cancellation leaves no child process or partial authoritative artifact.

## Workstream 6 — Rebuild the verification hierarchy

Priority: P1
Depends on: Workstreams 1-5

### Required changes

1. Standardize test classes as:
   - `unit`;
   - `contract`;
   - `integration`;
   - `end_to_end`.
2. Use pytest markers as the canonical machine-readable classification.
3. Remove the conflicting `live_truth` textual vocabulary or define it as a separate proof attribute, not a test layer.
4. Migrate tests in bounded directories and then turn on strict CI enforcement.
5. Fix the no-op checker to ignore type-only signatures and protocols.
6. Make architecture checks say `structural` in their names and reports.
7. Add composed-path subprocess and concurrent-app proof.
8. Restore Ruff to green; do not suppress categories merely to clear the count.

### Acceptance gates

1. Taxonomy strict mode reports zero missing classifications.
2. Every end-to-end test launches a real public surface.
3. Mock-heavy tests cannot be labeled end-to-end.
4. No-op and boundary checks have zero known false positives.
5. Ruff and the canonical pytest suite pass in the same worktree.

## Workstream 7 — Replace append-only authority prose with generated authority

Priority: P1
Depends on: Workstream 3

### Required changes

1. Create one small authority manifest containing:
   - install commands;
   - installed entrypoints;
   - runtime ownership;
   - durable paths;
   - active contracts;
   - compatibility aliases and expiry;
   - canonical verification commands.
2. Generate the human `CURRENT_AUTHORITY.md` snapshot from the manifest.
3. Move slice histories and detailed implementation inventories to release/closeout records.
4. Validate:
   - unique keys and numbering;
   - path existence;
   - contract status;
   - source references;
   - entrypoint parity;
   - compatibility expiry.
5. Cap the human snapshot to a reviewable size.

### Acceptance gates

1. Hand edits to generated authority output fail CI.
2. The manifest and rendered document cannot drift.
3. No historical implementation journal remains in the live snapshot.
4. Every canonical command has a corresponding live or explicitly blocked proof record.

## Workstream 8 — Decompose authority hotspots

Priority: P2
Depends on: Workstreams 2-7

### Required changes

Decompose in this order:

1. `orket/interfaces/api.py`;
2. `orket/interfaces/orket_bundle_cli.py`;
3. `orket/application/workflows/orchestrator_ops.py`;
4. `orket/application/workflows/turn_tool_dispatcher.py`;
5. `orket/application/workflows/turn_message_builder.py`;
6. runtime truth and evidence collectors with functions over 200 lines.

Decomposition rules:

1. Split by authority and resource lifecycle, not file-size target alone.
2. Keep one public facade only where it is a stable contract.
3. Do not introduce `__getattr__` proxies or copied compatibility implementations.
4. Preserve behavior with integration/end-to-end parity proof.
5. Do not grow an oversized file during extraction.

### Acceptance gates

1. New Python files remain under 400 lines.
2. New functions remain under 70 lines unless a reviewed correctness exception exists.
3. No class exposes more than 10 public methods without approval.
4. Import graph complexity and cycle count decrease after every slice.

## Recommended execution slices

### Slice A — Failure must fail

Status: Complete on 2026-07-30.

1. Fix first-run async settings.
2. Propagate typed CLI failures.
3. Add subprocess exit tests.
4. Fix quickstart help/EOF.
5. Package the governed-run scenario.

This is the smallest shippable risk reduction.

### Slice B — Real API instances

1. B1 complete: introduce application runtime container.
2. B1 complete: create new FastAPI objects per call.
3. B1 complete: prove two-app identity, owner, concurrency, and bounded teardown.
4. B2 complete: move service/store factories and extension/client teardown into the
   application composition root.
5. B2 complete: remove the module-default owner aliases and eager import-time engine.

### Slice C — Architecture gate cutover

1. Ratify current-layer mapping.
2. Implement allowed-edge enforcement.
3. Convert every temporary violation to an explicit exception.
4. Update architecture and contract deltas.

### Slice D — Core and async cleanup

1. Extract core effects.
2. Remove sync I/O from proven async paths.
3. Add determinism and responsiveness proof.

### Slice E — Verification and authority cleanup

1. Align taxonomy and CI.
2. Fix noisy gates.
3. Generate authority snapshot.
4. Begin hotspot decomposition.

## Required proof envelope per slice

Every slice must record:

1. requirements or contract ids addressed;
2. changed authority edges;
3. path classification: `primary`, `fallback`, `degraded`, or `blocked`;
4. observed result: `success`, `failure`, `partial success`, or `environment blocker`;
5. process exit status;
6. durable effects and teardown;
7. test classification for each new/modified test;
8. live, structural, and absent proof stated separately;
9. remaining exceptions with owner and removal trigger;
10. exact files touched.

Routine proof must set `ORKET_DISABLE_SANDBOX=1`. Any intentional sandbox acceptance run must prove teardown in the same execution path.

## Final exit criteria

The lane is complete only when:

1. all installed canonical commands are usable outside the checkout;
2. fatal command failures return nonzero;
3. API factories create isolated instances with complete teardown;
4. interfaces contain transport shaping, not application composition;
5. core is mechanically pure and deterministic over explicit inputs;
6. the dependency gate enforces the same allowed graph documented by architecture;
7. no unowned architecture exception exists;
8. strict test taxonomy, Ruff, documentation hygiene, and canonical pytest pass together;
9. `CURRENT_AUTHORITY.md` is generated from a small validated manifest;
10. the user accepts the live proof and explicitly closes the implementation lane.

## Stop conditions

Stop and reassess rather than widening scope if:

1. a slice requires a second authority implementation;
2. compatibility behavior cannot be removed without an explicit user decision;
3. a green gate requires weakening its policy;
4. tests pass only by replacing live paths with mocks;
5. an API/CLI change alters a durable contract without a contract delta;
6. unrelated user work would need to be overwritten.
