# ATG-06 canonical typing closeout

Date: 2026-10-01 (America/Denver)
Status: Source and structural proof passed; v0.6.123 publication pending
Owner: Orket Core

## What changed

Resolve all 49 frozen typing groups and the eight canonical remainder diagnostics
in five existing owners. Reuse canonical runtime/policy contracts, describe native
owner and result values, and remove incomplete local JSON Schema/JWT stub overrides
that shadowed already-declared dependency types. Preserve the Mypy configuration;
no new ignore, suppressed category, compatibility shim or Any escape.

Required-value corrections have native proof: missing API owners refuse admission,
missing epic snapshots refuse success publication, and invalid controller schema
roots refuse validation. Missing attempt references preserve authority-conflict
outcomes; null model scores remain invalid rows. Contract/migration details are in
`docs/architecture/CONTRACT_DELTA_TYPING_REQUIRED_VALUES_2026-10-01.md`.
Both Quality startup selections retain the new API-owner module. No new runtime
entrypoint, provider fallback, persistence authority or cleanup policy is added.

## What was verified

Canonical `python -m mypy orket/ --ignore-missing-imports` exits zero across
**1,222 source files**, after the refreshed opening count of 419 diagnostics in
175 files. The frozen earlier count of 415 in 170 files remains historical; the
inventory separately records removed, relocated and introduced diagnostics.
This is structural typing proof, not proof of every untyped function body.

All 49 selected source batches have passing affected controls. Local receipts
retain exact commands, processes, unchanged input hashes, logs, XML and failures.
The final canonical reconciliation selection passes **178 tests**, and the Quality
selection/API-owner check passes **33**. These overlap earlier selections and are
not a full-suite or aggregate distinct-test claim. Windows Python 3.11 controls
exercise real files, SQLite, Git, HTTP, child processes, cancellation and cleanup.
Applicable POSIX ownership/reload controls pass on Linux Python 3.11 source.
Individual unit/contract tests remain limited to their stated observations.

The intentionally failing API/snapshot/schema counterexamples are retained. B19's
initial 106-pass/two-failure run exposed a test comparing a pre-save revision with
the stored revision; reading the retained record before the operation corrects the
observation, and its scoped recheck passes. No assertion or timeout was weakened.
Per-batch counts and proof limits live in `VERIFICATION.json` and the worksets.

Healthy observed path: primary/success. Adverse controls retain expected failure,
refusal or partial effects. Controlled HTTP and fixture-model acceptance do not
establish llama.cpp inference. Linux source tests do not establish fresh packages.
All eight structural gates pass with unchanged inputs: canonical Ruff,
dependency direction (1,222 files, 4,276 edges, zero violations/cycles/errors),
strict taxonomy (12,139 items, zero missing/conflicting labels), critical no-op,
docs hygiene, authority structure, generated equality and release policy. No
modified Python file grows above 400 lines; the one-field Orchestrator declaration
remains below that limit. Publication is the only remaining ATG-06 exit action.

## What was not verified

No new complete source coverage run: ATG-07 owns the unchanged 89% gate. No fresh
installed Windows/Linux matrix, live llama.cpp inference or hosted Gitea Quality
execution. Canonical Mypy accepts the configured scope; its notes identify untyped
bodies it does not check. No repository-wide size or general runtime-truth claim.

## Remaining blockers or drift

Coverage remains at the historical failing observation until ATG-07. The default
llama.cpp endpoint is unavailable, hosted Gitea access is unestablished, and current
Linux clock/installed acceptance remains open. Deferred marshaller process teardown
and the authority checker's structural-only scope remain unchanged. None blocks
eligible local ATG-07 work after this checkpoint is published.

## Exact files touched

`VERIFICATION.json` records the exact file list and modified source hashes, all
49 workset records, the canonical remainder, and each retained proof campaign.
Version/changelog, contract/authority, Quality selection, active queue and ATG-05
publication readback accompany the scoped runtime/type changes.
