# Workflow and benchmark readiness

Last updated: 2026-10-04
Status: Active

`scripts/governance/check_workflow_preflight.py --project <project> --epic <name>`
loads canonical assets and acceptance schemas, checks the small-team reviewer
policy, and checks all declared team roles against the executable tool bindings.
Its result is structural: it does not prove inference, provider reachability,
turn routing, artifact correctness or completion. An unused invalid declared role
can also make this conservative check refuse. Runtime acceptance remains authoritative.

The stored `standard` and `qa_completion_test` epics are bounded integer-addition
CLI examples. Prepare inputs with `examples/stored_workflows/prepare.py` in a new
directory, then use `orket runtime`. Standard declares the interface, implements
it and verifies six examples. QA verifies a seeded CLI and retains a structured
handoff with explicit scope. Historical unbounded versions and failed runs remain
in Git and 0.7.4 evidence. Change acceptance with real task requirements; these
examples do not establish arbitrary-project completion.

The prepared `sanity_test` workflow writes one organization receipt with declared
text acceptance. Preparation captures the project organization name. Its receipt
explicitly limits the claim to file writing; it is not a general health check.

`challenge_workflow_runtime` is a fourth prepared recipe. It retains the twelve
dependent programming cards and their existing runtime commands/assertions. The
first three cards declare exact requirements text, design data and fixtures;
those are artifact checks, not proof of design quality. Subsequent cards declare
retained CLI acceptance over the cumulative implementation inventory. Preparation
seeds `challenge_acceptance_runner.py`, which invokes the canonical
`RuntimeVerifier` with the authored contract and retains inner command receipts
on stderr in the outer acceptance package. It seeds no solution code. The
development environment must include pytest for the original generated-test
commands. Passing those generated tests does not establish exhaustive correctness.
Use a fresh prepared project; raw legacy workspaces do not acquire this verifier
or acceptance retroactively. Never edit its verifier during model work.
The recipe records `ORKET_CONTEXT_WINDOW=1` for the selected 8K context. Apply
the printed runtime environment before launching its CLI or API process.
This uses the existing history-window control; required file context and
acceptance stay intact, and retained transcripts are not truncated.

Live card and collection benchmark runners retain each invocation's project,
assets, empty initial board and durable root under its canonical run directory.
They never adopt temporary assets into the caller's board or delete referenced
assets. An existing project path refuses creation. Function tasks require explicit
`function_examples` and expected results. CLI tasks require `cli_examples`,
`agent_output/main.py`, a declared artifact inventory, and exact stdout, stderr and
integer exit codes for every case. `scripts/benchmarks/task_acceptance.py` supplies
the sole benchmark adapter to the existing Python CLI acceptance service. It
captures the verifier and all declared implementation modules before execution.
Text process output uses Python's universal-newline handling; expected strings
are literal data, with no escape decoding or trimming at runtime. Existing quality
checks additionally replay each CLI case twice. Final validation still requires
unchanged verifier bytes, required harness reports, quality checks and successful
runtime exit. Metadata-only and undefined shapes refuse before inference.

`scripts/benchmarks/cli_example_checks.py` separately reports exact expected
outputs and observed replay equality. It observes both executions of every
declared case, including cases after a wrong answer. Both executions must match
the expected exit/stdout/stderr for correctness. A repeatable wrong answer fails
correctness while passing the bounded replay observation. Missing observations
fail with explicit incomplete details; they are not claims of nondeterminism.
Task success still requires both checks. Two matching executions do not prove
general determinism, and old conflated verdicts remain historical evidence.

When the separate support verifier is enabled, a CLI benchmark supplies an
issue-level command for its first declared case with exact JSON assertions.
This replaces the invalid default of invoking an argument-taking CLI with no
arguments. Full card acceptance still executes every declared case, including
nonzero exit/error cases. Prepared examples change the modular architecture
policy actually loaded by `ConfigLoader`; the generic support check is disabled
for the three small recipes while mandatory card acceptance remains enabled.
The challenge keeps support verification enabled and selects a CLI surface.
Preparation captures the
canonical loaded organization, not a lower-precedence legacy copy.

The ten v2 CLI tasks declare `main.py` plus `implementation.py`. Nine authored
tasks had literal backslash-n suffixes where their CLI examples intended a line
ending; the 0.7.6 task-bank correction changes those authored expected values to
actual newline characters. Old inputs/results remain historical evidence. The
runtime does not normalize away this distinction or fabricate expected results.

The canonical required `if __name__ == "__main__":` feature is checked as a
top-level Python equality guard, accepting either quote style or operand order.
Comments, string literals, nested guards and malformed Python do not satisfy it.
Other required/forbidden tokens retain their existing substring semantics. This
source-quality check is separate from behavioral acceptance; corrected rescoring
must retain the original verdict and identify the checker change.

`benchmarks/phase5_load_test.py` separates transport samples from work outcomes.
Without `--epic-id`, trigger requests verify HTTP 404 for nonexistent targets.
With a real target, it follows `/v1/runs/{session_id}/view` until accepted completion,
an unaccepted terminal state or an observation deadline. Admission alone does not
pass. Use one target/job at a time with a one-slot model. Error rates count each
attempted request once. Failed samples make the harness exit nonzero. The stress
launcher uses requested ports, refuses occupied ports, disables routine sandbox
creation and waits for its own children at cleanup.

`scripts/streaming/diagnose_llama_stream.py` records selected-server occupancy,
first content/reasoning delta time, duration and exception class for at most twenty
one-token requests. It refuses inference unless idle occupancy is confirmed. The
ten-second read limit matches the runtime cap. It does not restart the server,
change its model or establish long-run endurance.

The streaming scenario runner owns one pending WebSocket receive across polling
deadlines. A polling timeout does not discard that receive or start another
consumer. Socket context exit precedes settlement of the pending reader; failure
to settle is an explicit harness error. Transport failures propagate. The runner
does not prefetch events, extend scenario deadlines, or weaken finalization and
post-cancel quiet assertions. Long-run reports retain earlier failed attempts.

`scripts/reviewrun/run_30page_consistency.py` retains Git history in `fixture.bundle`,
with its SHA-256 and commit identities in `fixture.json`. By default it generates
a new baseline and records the generator hash. With `--historical-report <path>`,
it recovers the report's exact commits from surviving objects in a separate
repository, without repairing or modifying the historical source. Missing objects
refuse recovery; there is no silent substitution. Reruns verify the bundle,
complete object graph and clean checkout; a missing checkout is restored from the
bundle. A moved repository can have a different snapshot identity despite identical
commit inputs. Reports identify policy, actual repeat count and first/last bundles.
Consistency is native deterministic execution,
not model-quality proof. Reports use the shared diff ledger and stable staging
paths. None of these commands promotes evidence or switches providers automatically.
