# Behavioral Review: Architectural Truth

Date: 2026-07-29
Status: Observed behavior snapshot; not an approved implementation lane
Scope: Local execution against the current working tree

## Verdict

Orket's bounded governed demos behave more truthfully than its canonical runtime shell.

The strongest behavior is at the edges that were recently built with explicit ledgers and evidence bundles. The weakest behavior is at older composition and startup seams: fatal errors can become successful process exits, app construction mutates global state, and installed commands depend on checkout-relative assets.

The behavioral risk is therefore inverted. The narrow demo tells a credible story, while the broad "default runtime" path—the path users and automation are told is canonical—does not meet the same truth standard.

## Observed behavior matrix

| Probe | Path class | Observed result | Proof | Assessment |
|---|---|---|---|---|
| Fresh `python main.py` from a temporary working directory | primary | failure with exit code `0` | live | Critical false success |
| `python main.py --help` | primary | help rendered, exit `0` | live | Success |
| `python server.py --help` | primary | help rendered, exit `0` | live | Success, but full app is composed before argument handling |
| Governed-action demo with denial input | primary demo | denied effect skipped, ledger written, exit `0` | live | Success |
| `python -m orket.quickstart.governed_action_demo --help` | primary demo | entered approval prompt, then `EOFError`, exit `1` | live | Failure |
| `orket run scenario <absolute scenario>` | primary demo | one allowed, one approval-required, one blocked; evidence bundle written | live | Success |
| `orket demo governed-run` outside the checkout root | primary demo | missing checkout-relative scenario, exit `1` | live | Portability failure with truthful exit |
| API `/health` | primary | `200 {"status":"ok"}` | live | Success |
| API `/v1/version` without an API key | primary | `403` | live | Success |
| Two `create_api_app()` calls with different roots | primary composition | same object; second root replaces first context | live | Failure |
| `python -m pytest -q` | verification | 4,365 passed, 53 skipped, two warnings | live local execution; mixed test layers | Success, but not entrypoint-complete proof |

`ORKET_DISABLE_SANDBOX=1` was set for routine runtime/test proof where applicable. No intentional sandbox resources were created.

## Ship-risk behavior

### BR-01 — First-run onboarding is broken when reached through the canonical runtime

Severity: Critical

Observed output included:

```text
[FIRST RUN] Orket EOS Orkestrated.
Command: python main.py --card initialize_orket

[FATAL] save_user_settings must run before the event loop starts or after set_runtime_settings_context().
```

Observed process exit:

```text
0
```

The cause is deterministic:

1. `main.py` starts the event loop.
2. `run_cli()` calls synchronous first-run setup inside that loop.
3. first-run setup calls the synchronous settings bridge;
4. the bridge correctly rejects event-loop use;
5. `run_cli()` catches the error and returns;
6. `main.py` sees a normal return and exits successfully.

This is a double failure:

1. onboarding uses the settings API in a prohibited context;
2. the CLI converts the resulting fatal error to success.

Existing tests validate onboarding as a synchronous function and validate `main.py` only when the delegated runner raises. They do not exercise the real composition of `main.py -> run_cli -> first-run onboarding`.

Required behavior:

1. A fresh runtime either completes onboarding and continues, or exits nonzero with one concise error.
2. No success-shaped onboarding narration may precede uncommitted persistence.
3. A subprocess test must assert the real exit code.

### BR-02 — API instances are not behaviorally isolated

Severity: Critical

The app factory probe created an app for root A and then an app for root B. Both variables referenced the same FastAPI object. After the second call, reading context through the first variable returned root B.

This means an app reference does not own its configuration. Its behavior depends on the most recent factory call anywhere in the process.

The risk is not limited to tests:

1. embedded servers cannot safely construct independent instances;
2. lifecycle and runtime owner teardown become ambiguous;
3. one configuration change can redirect another caller's store/workspace;
4. orphaned engines can retain resources.

Required behavior:

1. `create_api_app(A) is not create_api_app(B)`.
2. Starting or using B cannot change A's project root, engine, queues, extension catalog, or outbound policy.
3. Closing each client closes only its own owners.

### BR-03 — The installed and canonical CLIs present different products

Severity: High

Observed:

1. `python main.py --help` describes card, epic, protocol, marshaller, board, loop, and archive runtime operations.
2. `orket --help` describes bundle validation, SDK, extensions, refactor, API generation, review, governed runs, replay, approvals, and connectors.

The documented install command creates `orket`, but the documented canonical runtime remains a source-tree script. A user can install Orket successfully and still not have an installed command for the canonical card runtime.

Required behavior:

1. One installed root command exposes the supported product.
2. Help identifies stable, compatibility, experimental, and unavailable surfaces.
3. Source wrappers and console entrypoints return identical exit semantics.

### BR-04 — The governed-run demo is checkout-relative

Severity: High

`orket demo governed-run` resolves its default scenario as `examples/governed-run/scenario.yaml` relative to the caller's current directory. It succeeded only when the caller was at the repository root. From a temporary directory it returned:

```text
FAIL [E_GOVERNED_RUN_FAILED]: governed-run scenario not found: <temp>\examples\governed-run\scenario.yaml
```

The exit code was correctly `1`. The truth defect is in packaging and documentation, not result signaling.

Required behavior:

1. Package the default scenario as a package resource.
2. Resolve it independently of current working directory.
3. Preserve an explicit `--scenario` override.
4. Add an installed-wheel subprocess test from an unrelated directory.

### BR-05 — The quickstart has no command-line contract

Severity: Medium

Passing `--help` starts the governed action instead of showing usage. In a noninteractive process it prompts and then raises `EOFError`.

The core approval/denial behavior is sound when input is supplied, but the entrypoint is brittle in discovery, CI, documentation tooling, and non-TTY invocation.

Required behavior:

1. Add normal argument parsing and `--help`.
2. Detect noninteractive stdin and return a structured nonzero error unless an explicit decision flag is supplied.
3. Add `--approve`/`--deny` only if the demo contract clearly labels them as scripted operator simulation.
4. Catch `EOFError` at the CLI boundary and do not emit a Python traceback for expected noninteractive use.

## Self-deception behavior

### BR-06 — Tests prove components while missing the composed entrypoint

Severity: High

Examples:

1. `test_main_logs_crash_and_exits` injects a runner that raises, so it proves `main.py` handles escaping exceptions. The real `run_cli()` swallows its fatal error, so that test cannot detect the observed false success.
2. first-run onboarding tests call the synchronous onboarding function outside an event loop, avoiding the production failure.
3. the API composition "isolation" test asserts the two apps are the same object.
4. governed-run CLI tests always pass an explicit temporary scenario, so they do not test the advertised default demo from an installed location.
5. quickstart tests inject an input function and do not exercise help or EOF behavior.

The suite is rich in local behavior tests but weak at composed operator paths. This allows thousands of passing tests to coexist with broken entrypoints.

The canonical suite passed 4,365 tests in the reviewed worktree. That is meaningful regression evidence; it is not evidence that the canonical entrypoints are healthy because the observed failure paths above are absent or intentionally encoded as acceptable.

Required behavior:

1. Every canonical command gets at least one subprocess end-to-end test.
2. Each factory gets a multiple-instance isolation test.
3. Each default resource is tested from outside the checkout.
4. Exit code, stdout/stderr classification, durable effects, and teardown are asserted together.

### BR-07 — Health is narrower than operator intuition

Severity: Medium

`GET /health` returned `200 {"status":"ok"}`. That proves the HTTP app responds. It does not expose whether the canonical engine, persistence, provider, extension runtime, or background workers are usable.

This is not necessarily wrong, but the route name is broader than the proof. The richer `/v1/system/health-view` surface should be the operator readiness authority, while `/health` should be explicitly labeled liveness-only.

Required behavior:

1. Document `/health` as process liveness.
2. Keep readiness/degraded state on a separate authenticated endpoint.
3. Never use liveness success as runtime-readiness evidence.

## Behavior worth preserving

### Governed-action denial

The denial path:

1. displayed the exact proposed file write;
2. accepted operator denial;
3. did not create the proposed file;
4. recorded `denied_skipped`;
5. wrote a hash-chained ledger;
6. returned success for successful execution of the denial policy.

This is good result semantics: the requested side effect was denied, but the governance operation itself completed successfully and truthfully reported the terminal state.

### Governed-run explicit scenario

The explicit scenario:

1. allowed read-only observation;
2. required approval for a write;
3. blocked an unallowlisted shell command;
4. wrote evidence, replay, summary, and transcript artifacts;
5. reported that replay did not replay side effects.

This is the behavioral standard the older runtime entrypoints should meet.

### API authentication

The local API returned liveness without authentication and rejected a `/v1` request without an API key. That matches the intended separation for the observed configuration.

## Behavioral acceptance standard

No remediation slice is complete unless its proof records:

1. path: `primary`, `fallback`, `degraded`, or `blocked`;
2. result: `success`, `failure`, `partial success`, or `environment blocker`;
3. process exit code;
4. stdout/stderr claims;
5. durable state effect or verified absence of effect;
6. teardown result;
7. whether proof is live, structural, or absent.

The first release gate should be simple: a command that prints `[FATAL]`, `FAIL`, or a traceback must not exit `0`.
