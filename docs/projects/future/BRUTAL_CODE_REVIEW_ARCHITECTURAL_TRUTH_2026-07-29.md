# Brutal Code Review: Architectural Truth

Date: 2026-07-29
Status: Review snapshot; findings are not an approved implementation lane
Scope: Current working tree, including pre-existing and uncommitted changes present during review

## Verdict

Orket has a large amount of serious, test-backed engineering, but its architectural control system is not telling the truth about the code it governs.

The main problem is not that the target architecture is unfinished. `docs/ARCHITECTURE.md` admits that. The problem is that machine checks, tests, and authority prose convert known and unknown divergence into green signals:

1. The dependency checker passes an import graph that does not implement the documented five-layer dependency model.
2. The API "factory" is a process-global mutable singleton, while its authority language calls ownership app-scoped and its isolation test treats global replacement as isolation.
3. The canonical CLI catches fatal startup failures below `main.py`, prints a fatal traceback, and returns process success.
4. Core code performs file I/O, emits logs, reads time directly, and imports implementation services despite the claim that core is deterministic and dependency-minimal.
5. Test taxonomy, lint, file-size, function-size, and no-op gates disagree with both policy and the repository they are supposed to govern.

The codebase is not devoid of architecture. It has several overlapping architectures: the five-layer target, the dependency checker's fifteen classifications, the legacy top-level package graph, the runtime subpackage migration, the control-plane model, and process-global compatibility surfaces. The lie is presenting those as one converged system.

## Review method and proof boundary

The review used:

1. Structural inspection of `docs/ARCHITECTURE.md`, `CURRENT_AUTHORITY.md`, runtime entrypoints, import policy, application/core/interface code, and tests.
2. Machine checks:
   - dependency direction checker over 778 Python files;
   - strict test-taxonomy checker over 4,113 tests;
   - no-op critical-path checker over 457 files;
   - Ruff over `orket/`;
   - runtime-boundary audit;
   - targeted architecture tests.
3. Live local probes of the canonical CLI, installed CLI surface, quickstarts, governed-run scenario, API security posture, and repeated API app construction.

No claim in this review treats inspection or mocked tests as live runtime proof.

## Ship-risk debt

### SR-01 — The canonical CLI reports fatal startup failure as process success

Severity: Critical
Proof: Live

`main.py` delegates to `asyncio.run(run_cli())` and only returns nonzero if an exception escapes (`main.py:13-20`). `run_cli()` catches `RuntimeError`, `ValueError`, `OSError`, and `TypeError`, prints a traceback and `[FATAL]`, then returns normally (`orket/interfaces/cli.py:227`, `orket/interfaces/cli.py:556-560`).

On a fresh temporary working directory, the first-run path calls synchronous `save_user_settings()` from inside the running event loop:

1. `run_cli()` calls `perform_first_run_setup()` at `orket/interfaces/cli.py:234`.
2. Onboarding calls `save_user_settings()` at `orket/discovery.py:170`.
3. The sync bridge rejects use in an active event loop at `orket/settings.py:60-76`.
4. The CLI prints `SettingsBridgeError` and `[FATAL]`.
5. The observed process exit code is `0`.

This directly violates the runtime-truth rule. It also defeats shells, automation, launchers, and any test that relies on process status.

Required correction:

1. Make the CLI application return a typed exit result or raise a typed fatal exception.
2. Keep exactly one top-level exception-to-exit-code boundary.
3. Move first-run persistence to an async API or execute it before event-loop startup.
4. Add a subprocess end-to-end test that proves a fresh working directory exits nonzero on failure and zero on success.

### SR-02 — `create_api_app()` is a singleton reset function disguised as an app factory

Severity: Critical
Proof: Live and structural

`orket/interfaces/api.py` constructs one module-global FastAPI object at line 592. `create_api_app()` mutates that object, replaces its context and engine, and returns the same object at lines 2049-2060.

A live two-root probe observed:

```text
same_app_object = true
first_context_replaced = true
app_one_now_points_to_second_root = true
first_engine_orphaned = true
```

The first caller does not retain an isolated application. Constructing a second "app" changes what the first reference sees. The displaced engine is not closed by `create_api_app()`.

This creates:

1. cross-test and cross-host state leakage;
2. root/configuration races if multiple apps are constructed in one process;
3. orphaned runtime owners;
4. a hard ceiling on truthful multi-app embedding;
5. false confidence from app-scoped terminology.

Required correction:

1. Build a new FastAPI instance per factory call.
2. Put routers, middleware, lifespan, runtime context, and runtime state on that instance.
3. Remove module-global runtime-owner adoption.
4. Close all instance-owned resources in lifespan teardown.
5. Add a concurrent two-app integration test proving root, engine, event queue, and extensions remain isolated.

### SR-03 — The interface layer is a composition and side-effect ownership layer

Severity: High
Proof: Structural

The target says interfaces translate requests into application contracts. `orket/interfaces/api.py` instead:

1. imports storage adapters directly at lines 18-21;
2. resolves decision nodes at lines 63 and 107;
3. constructs stores and application services at lines 637-685;
4. constructs `CommitOrchestrator`, `ExtensionManager`, stream owners, and the engine;
5. holds mutable compatibility aliases at lines 704-709;
6. eagerly constructs an engine at line 847.

`orket/runtime/policy/composition.py` then imports interface modules dynamically to create the API and CLI. Composition authority is split between a runtime-policy module and the interface module it constructs.

This is not a narrow transport compatibility exception. It is the actual composition root and live ownership model.

Required correction:

1. Establish one application-owned composition root.
2. Inject application facades into thin routers.
3. Prohibit interface imports of adapters, decision nodes, kernel implementations, and orchestration implementations except through explicitly documented bootstrap modules.
4. Delete or explicitly time-box module-global compatibility aliases.

### SR-04 — Core is not deterministic, dependency-minimal, or side-effect free

Severity: High
Proof: Structural with reachable call path

Examples:

1. `orket/core/domain/failure_reporter.py` reads wall clock, creates directories, writes JSON with `aiofiles`, and emits a log event (`:17`, `:23`, `:39-85`).
2. It is called by the application failure handler at `orket/application/services/orchestrator_failure_handler.py:65`.
3. `orket/core/policies/tool_gate.py` imports `orket.services.ast_validator` and `orket.services.idesign_validator` at lines 15-16.
4. Additional core modules emit events and use direct wall clock, including `bug_fix_phase.py`, `fixture_verifier.py`, `execution.py`, and `sandbox.py`.

These are direct contradictions of sections 5, 7, 11, and 13 of `docs/ARCHITECTURE.md`, and they are not named in Known Current Exceptions.

Required correction:

1. Move artifact writing and event publication to application services.
2. Keep core failure reporting as pure data construction.
3. Move implementation validators behind core contracts or into application authority.
4. Inject clock values into core transitions.
5. Make core imports mechanically allowlist-based, not merely denylist-based.

### SR-05 — Async-reachable code still performs synchronous I/O

Severity: High
Proof: Structural with direct async reachability

Examples:

1. Async settings routes call `runtime_policy_options()` synchronously (`orket/interfaces/routers/settings.py:63-64`, `:88`).
2. That application service reads JSON through `Path.read_text()` (`orket/application/services/runtime_policy.py:120-125`).
3. `run_cli()` is async but calls synchronous extension installation at `orket/interfaces/cli.py:173` and `:227`.
4. `ExtensionManager` uses `subprocess.run()` and synchronous file hashing (`orket/extensions/manager.py:295-322`).

The repository scan found 22 `subprocess.run()`/`subprocess.call()` uses under `orket/` and 97 raw/synchronous file-I/O matches under application, runtime, orchestration, and interfaces. Those counts are inventory, not proof that every match is live event-loop reachability; the settings route above is a proven reachable example.

Required correction:

1. Convert request-reachable file access to `aiofiles` or `asyncio.to_thread`.
2. Convert subprocess work to `asyncio.create_subprocess_exec`.
3. Add an AST/import reachability gate for prohibited sync APIs in async-reachable roots.
4. Maintain an explicit, small exemption file for genuinely CLI-only code.

### SR-06 — The installed command surface and canonical runtime surface do not converge

Severity: High
Proof: Structural and live

The documented default runtime is `python main.py`, but the installed `orket` console script maps to `orket.interfaces.orket_bundle_cli:main` (`pyproject.toml:45`). They expose unrelated command trees:

1. `python main.py --help` exposes card/epic/runtime flags.
2. `orket --help` exposes bundle, SDK, review, governed-run, and extension commands.
3. A user outside the source checkout has the `orket` console script but no guaranteed `main.py` path.

The product therefore has an installed CLI and a canonical runtime CLI without a single operator authority.

Required correction:

1. Choose one installed root command.
2. Make card runtime, governed demos, review, and extension operations explicit subcommands of that root.
3. Retain source-file entrypoints only as thin compatibility wrappers with an approved removal window.

## Self-deception debt

### SD-01 — The dependency checker passes because it checks a weaker architecture

Severity: Critical
Proof: Structural and executed gate

`docs/ARCHITECTURE.md` defines five layers and a mostly allowlisted dependency direction. `model/core/contracts/dependency_direction_policy.json` classifies the code into many additional layers, including `agents`, `domain`, `infrastructure`, `kernel`, `orchestration`, `platform`, `runtime`, `services`, and `vendors`. It then forbids only selected pairs.

The checker reports success whenever no explicitly forbidden pair or unknown classification exists (`scripts/governance/check_dependency_direction.py:47-48`, `:114`, `:158-177`). It does not compare the observed graph with the architecture's allowed edge set.

Observed passing graph examples:

| Edge | Count | Target-architecture status |
|---|---:|---|
| `runtime -> application` | 26 | Undeclared |
| `runtime -> adapters` | 17 | Undeclared |
| `adapters -> runtime` | 14 | Disallowed by the allowed-direction model |
| `interfaces -> adapters` | 10 | Disallowed by the allowed-direction model |
| `interfaces -> runtime` | 6 | Disallowed by the allowed-direction model |
| `runtime -> orchestration` | 5 | Undeclared |
| `core -> services` | 2 | Core implementation dependency hidden by an extra layer |
| `runtime -> interfaces` | 2 | Reverse dependency |

The gate scanned 778 files, returned zero violations, and passed.

Required correction:

1. Replace the denylist with allowed edges derived from the normative architecture.
2. Treat transitional layers and edges as explicit expiring exceptions with owner and removal condition.
3. Fail on cycles between authority layers.
4. Publish both allowed exceptions and unexpected edges in the report.

### SD-02 — The API isolation test codifies non-isolation

Severity: High
Proof: Test inspection and live probe

`tests/interfaces/test_api_composition_isolation.py` calls the factory for two roots and explicitly asserts `app_a is app_b` at line 37. The test is named as isolation proof while it validates replacement of one process-global context.

This is worse than missing coverage: the test protects the defect from correction.

Required correction:

1. Rename the current test as a legacy-singleton characterization until removal.
2. Add the real isolation test first.
3. Delete the characterization when the singleton is retired.

### SD-03 — Test taxonomy is declared, partially imitated, and not enforced

Severity: High
Proof: Executed gate

`pyproject.toml` declares `unit`, `contract`, `integration`, and `end_to_end` markers (`:103-108`). The taxonomy script recognizes textual labels `unit`, `contract`, `integration`, and `live_truth`, but not `end_to_end` (`scripts/governance/enforce_test_taxonomy.py:11`).

The strict taxonomy run observed:

```text
tests_total = 4113
missing_layer_total = 3344
unit = 94
contract = 482
integration = 193
unlabeled = 3344
```

The new governed-run test says `Layer: end-to-end`, which the checker itself does not recognize. No Gitea workflow invocation of `enforce_test_taxonomy.py` was found.

Required correction:

1. Choose pytest markers or one exact textual convention, not both.
2. Align the vocabulary with repository policy.
3. Enforce the gate in CI after a bounded migration.
4. Prevent structural/mock-heavy tests from using integration or end-to-end labels.

### SD-04 — `CURRENT_AUTHORITY.md` is an append-only change log presented as a narrow snapshot

Severity: High
Proof: Structural

The file says it is "intentionally narrow" and should name live seams rather than reproduce implementation detail (`CURRENT_AUTHORITY.md:7-11`). It is 1,167 lines long, contains 62 `Canonical ...` numbered entries, and devotes giant paragraphs to slice history and file inventories.

Consequences:

1. canonical truth is hard to review;
2. obsolete clauses can survive inside long paragraphs;
3. the machine-readable map and prose can drift independently;
4. every change increases merge and audit risk;
5. "canonical" loses discriminating value.

Required correction:

1. Make a small machine-readable authority manifest canonical.
2. Render the human snapshot from it.
3. Move historical detail to release/closeout records.
4. Enforce uniqueness, path existence, schema validity, and maximum human-document size.

### SD-05 — Quality gates are red or noisy while selected architecture tests remain green

Severity: Medium
Proof: Executed gates

Observed:

1. Ruff found 131 errors under `orket/`; the quality workflow includes Ruff.
2. The no-op critical-path checker returned 15 findings, all from ellipsis signatures inside `if TYPE_CHECKING` mixin blocks. The checker does not understand that type-only pattern and returns a false red.
3. The targeted architecture tests passed 11/11.
4. The runtime-boundary audit passed by checking five declared paths and their metadata, not behavior or exception handling.
5. The canonical pytest command passed 4,365 tests and skipped 53, with two warnings. That broad green suite did not detect the live first-run false-success path or reject the API singleton behavior.

The problem is not merely red CI. It is a proof system where green checks are narrow, red checks are normalized, and names overstate what was proven.

Required correction:

1. Make every required gate runnable and green before treating it as authority.
2. Fix false positives rather than teaching contributors to ignore them.
3. Rename structural checks so their output does not imply runtime proof.

## Exploration-safe debt

### ES-01 — Decision nodes remain environment-sensitive strategy objects

Severity: Medium
Proof: Structural; partially acknowledged

`DecisionNodeRegistry` reads settings to select nodes, and built-in nodes read environment variables for orchestration limits. `docs/ARCHITECTURE.md` acknowledges part of this in Known Current Exceptions, but the registry reach-through is broader than the two named files imply.

The short-term risk is replay ambiguity, not immediate data corruption. Keep the exception explicit, inject resolved configuration snapshots, and stop expanding environment reads.

### ES-02 — The code is physically too large to make authority review cheap

Severity: Medium
Proof: Structural

Observed:

1. 778 Python files under `orket/`.
2. 76 Python files exceed 400 lines.
3. 237 functions exceed 70 lines.
4. Largest examples include:
   - `orket/interfaces/api.py`: 2,088 lines;
   - `orket/application/workflows/orchestrator_ops.py`: 1,853 lines;
   - `orket/interfaces/orket_bundle_cli.py`: 1,555 lines;
   - `runtime_truth_contract_drift_report()`: 931 lines;
   - `execute_tools()`: 543 lines;
   - `prepare_messages()`: 529 lines.

Size is not automatically wrong. Here it hides authority decisions, makes path reachability hard to prove, and encourages tests that validate local fragments while missing entrypoint behavior.

Decomposition must follow corrected ownership boundaries. Splitting files before deciding authority would merely distribute the same ambiguity.

## What is working and should be preserved

1. The governed-action denial path skipped the write and emitted a verifiable ledger in a live temporary workspace.
2. The explicit governed-run scenario produced evidence, replay, summary, and transcript artifacts without replaying side effects.
3. API health returned `200`, while `/v1/version` without an API key returned `403`.
4. The runtime-boundary inventory and dependency graph scripts provide useful raw inputs even though their pass semantics are too weak.
5. The codebase often distinguishes authored truth from projections and support evidence. That discipline should be applied to architecture and test claims too.

## Bottom line

Do not start with a repo-wide refactor.

First make failures fail, factories create, checks enforce the stated model, and authority files describe current truth. Only then decompose the large modules. Otherwise Orket will produce cleaner code that preserves the same architectural lies.
