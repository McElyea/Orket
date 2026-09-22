# Runtime architecture policy inputs

Last updated: 2026-09-22
Status: Implementation contract; acceptance remains in the architectural-truth plan

Architecture resolution consumes an explicit immutable snapshot of the microservices
unlock decision. Policy options also consume the separately observed pilot-stability
decision. These value functions cannot read environment variables, report files or
hidden caches to fill missing context. Missing required input is an error, not a
locked-policy default invented by the evaluator.

Application observation retains the existing boolean environment-override precedence,
report normalizers, architecture aliases and locked-mode behavior. An explicit unlock
override avoids the unused unlock-report read. Orchestrator architecture observation
does not read an unused pilot report. Missing, malformed JSON and non-object reports
retain their existing locked/unstable interpretation; other read failures propagate.
There is no new permissive fallback or alternate readiness authority.

An observation owner receives a copied environment and an absolute invocation root.
Relative report paths bind to that root before I/O; later environment or working-
directory changes cannot redirect the observation. File reads and report normalization
run through an owned worker for async callers. Native observation refuses event-loop
entry before reads. Cancellation, timeout and shutdown retain admitted work until its
actual termination; an unrelated SQLite operation must meet the predeclared 0.5-second
latency bound while a report read is held.

Each settings request captures its current policy environment and invocation root
at admission, preserving operator policy changes between requests. It observes each
needed report once and uses that same immutable policy/environment input for validation,
effective values, options and returned metadata. Existing conditional settings writes
and conflict refusals remain authoritative. This is not an atomic transaction over
multiple report files or protection against unrelated filesystem mutation.

Orchestrator composition supplies the architecture snapshot explicitly. Architecture
mode and allowed-pattern context use that same value instead of independently reading
the environment or readiness reports. The native composition boundary owns any required
observation; direct orchestrator construction requires the snapshot.

Acceptance requires actual request and file flows, unchanged readiness interpretation,
identical-input value parity, explicit missing-input refusal, captured-input behavior
through suspension, and retained workers under cancellation/timeout/shutdown. Installed
source binding, BT-1 through BT-5 and previous scoped guarantees remain required.
This contract does not establish full D acceptance, Linux clock repair, provider-backed
CAP acceptance, whole-plan completion or lane retirement.
