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

Live card and collection benchmark runners retain each invocation's project,
assets, empty initial board and durable root under its canonical run directory.
They never adopt temporary assets into the caller's board or delete referenced
assets. An existing project path refuses creation. Supported function tasks require
explicit `function_examples` and expected results. The existing Python CLI
acceptance service executes those cases. Final benchmark validation also requires
unchanged verifier bytes, existing quality checks and successful runtime exit.
Metadata-only and other program shapes refuse before inference until they have
suitable task-specific acceptance. No fabricated expected results are supplied.

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
