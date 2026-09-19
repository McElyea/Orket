# Epic bootstrap and summary time inputs

Last updated: 2026-09-19
Status: Active contract; scoped acceptance belongs to the architectural-truth plan.

The standard `ExecutionPipeline` receives a `RuntimeInputService`. Epic bootstrap
captures one `utc_now()` value from that service before invoking
`capture_run_start_artifacts(now=...)` in its owned worker. Run identity and the
workspace snapshot consume this explicit value. Bootstrap must not bypass the
selected input service with a second implicit clock read.

The worker remains owned through repeated cancellation and timeout. Directory
publication retries preserve that captured timestamp. A worker failure remains
unresolved; published bootstrap files can precede interruption of ledger startup.
The publication budget, refusal and retained-evidence contract is
`docs/architecture/CONTRACT_DELTA_RUN_START_PUBLICATION_D_2026-09-19.md`.

Epic outcome observation and preparation/publication continue to use that
service's existing UTC input seam. Protocol-ledger event timestamps have their
own explicit `timestamp_factory` port; callers supplying controlled time must
configure both ports consistently for the behavior they are proving. Neither
injected fixture timestamps nor UTC subtraction prove monotonic elapsed time.

An existing immutable `run_identity.json` keeps its original start time when
read again. This change does not rewrite old identity, outcome, ledger or summary
artifacts and introduces no new schema or automatic historical repair.

Summary generation still refuses missing or negative intervals. The separate
generation error is retained; its fallback has `is_degraded: true` and
`duration_ms: null`, preserving the original status and failure reason. That
minimal degraded summary need not contain optional packet projections. It must
not manufacture a nonnegative duration or change a failed run into success.
These failure semantics are defined in `CORE_RUNTIME_STABILITY_REQUIREMENTS.md`.

This boundary does not guarantee a nondecreasing operating-system UTC clock,
explain historical clock reversal, make UTC a monotonic latency measurement,
or close the remaining explicit-input and clock inventory under D. Default
`RuntimeInputService` behavior remains the host UTC clock; controlled clocks
are caller-provided inputs rather than hidden global overrides.
