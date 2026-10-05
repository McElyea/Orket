# Workflow readiness and outcome reconciliation

Owner: Orket Core
Date: 2026-10-04
Effective patch: 0.7.5

## Delta

API `/system/run-active` previously acknowledged nonexistent targets and scheduled
raw tasks whose early errors could disappear from ownership. Canonical card/epic/
issue/rock invocations now resolve their target before acknowledgment, returning
404 on `CardNotFound`. Existence is an observation, not an atomic reservation;
later changes can still make execution fail. API jobs use the existing background
supervisor, which retains failures, closes admission on an owned failure,
diagnoses it and refuses a falsely clean teardown. Owned invocation finalization
removes per-session task bookkeeping. The durable run ledger and completion
projection remain authoritative; no competing job store is introduced.

Real streaming failures retain their exception class even with an empty message.
Deadlines, provider selection, fail-closed behavior and cleanup remain unchanged.
The direct provider diagnostic records occupancy and first-token timing without
changing the server or widening deadlines.

Benchmark isolation, acceptance, conservative preflight, bounded stored examples
and retained fixtures follow `docs/specs/WORKFLOW_BENCHMARK_READINESS.md`.
These repairs do not reopen PRR-S1 or deferred architectural-truth work.

Recovered historical review inputs exposed a separate false-green defect: the
forbidden-pattern scanner treated `files` snapshots as unified patches and missed
their retained TODO/FIXME text. It now scans bounded selected context blobs for
that source, retaining path/line attribution. Diff/PR scans still inspect only
added lines. Policy digests and old evidence are unchanged; fresh decisions can
correct earlier false passes. The long-run tool can require an explicit expected
decision in addition to consistency. Contract: `docs/specs/REVIEW_RUN_V0.md`.

## Migration and validation

Clients must handle missing-target HTTP 404. Load consumers distinguish refusal
controls, transport performance and accepted completion. Function benchmark
admission intentionally refuses undefined tasks before inference. Prepare stored
workflow inputs and supply task-specific acceptance for new work.

Validation includes native Windows model runs, TCP API/load observations,
consecutive isolated benchmark invocations, deterministic review repeats and
native failure/transport tests. Exact outcomes and limits belong to the 0.7.5
proof report; source inspection alone does not establish live proof.

## Rollback and versioning

Revert through a newly versioned patch if demonstrated regressions require it.
Preserve projects, bundles, failed attempts and published evidence. Do not restore
HTTP-only success claims or overwrite the accepted 0.7.2 package pair. The SDK
contract and selected provider are unchanged. This is a patch release.
