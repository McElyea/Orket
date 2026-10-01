# Runtime architecture policy inputs

Last updated: 2026-09-28
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

The API router passes these captured inputs to `ApiRuntimeContainer`, which owns
construction and settlement of the request's `RuntimePolicyInputService`. The
router does not construct that runtime implementation. Moving this composition
boundary preserves per-request observation, native I/O ownership and response
contracts; it introduces no shared policy cache or construction-time policy freeze.

Orchestrator composition supplies the architecture snapshot explicitly. Architecture
mode and allowed-pattern context use that same value instead of independently reading
the environment or readiness reports. The native composition boundary owns any required
observation; direct orchestrator construction requires the snapshot.

Orchestrator runtime, prompt and protocol policy selectors receive selected values
at their existing phase or callback boundary. Their extraction does not freeze
organization/settings values earlier, reorder observation precedence or replace
the explicit architecture snapshot. Existing ambient settings behavior outside
that snapshot remains a separate input-ownership obligation.

`OrchestratorSupportServices` constructs canonical scaffolder, dependency, deployment
and runtime-verifier implementations directly, once, with all selected inputs.
An internal constructor `TypeError` propagates unchanged; it cannot trigger a
second construction with fewer arguments. Direct support construction takes no
class-getter compatibility hooks. Tests and embeddings use the actual construction
owner or canonical class methods, not removed facade class/settings exports or
private policy forwarders. Orchestrator itself owns ordered card transition and
control-plane publication plus public verification; helper policy selection grants
no storage or completion authority. Migration and scoped evidence:
`docs/architecture/CONTRACT_DELTA_ORCHESTRATOR_POLICY_E2_2026-09-28.md`.

Canonical workspace setup services (`Scaffolder`, `DependencyManager` and
`DeploymentPlanner`) resolve their existing detached specification before the
first await. They capture the selected workspace and standard `AsyncFileTools`
capability through the existing file-root/tool capture authority, then retain
the complete stage with the shared I/O owner. Root selection, generated content,
profile/pinning rules, existing-file preservation and validation ordering remain
unchanged. Ordinary relative roots bind at admission; drive-relative roots use
the existing explicit file-root refusal. No new workspace path policy is added.

A stage retains its metadata, directory creation, file open/write/close and final
validation through repeated cancellation or timeout. Its successful post-cancel
value is discarded; an actual operation or validation failure retains precedence.
Earlier created files remain when a later operation fails; this is not a multi-file
transaction or rollback promise. The epic setup coordinator does not proceed to
the next stage or publish the interrupted stage as completed. Policy/environment
selection and setup logging outside these service attempts remain separate
obligations. Custom stage implementations still enter through the existing
support-service construction seam; canonical capture does not clone arbitrary
subclasses, instance hooks or unknown writer protocols. Scoped migration/proof:
`docs/architecture/CONTRACT_DELTA_WORKSPACE_SETUP_D_2026-09-28.md`.

Team replan composition uses one `TeamReplanScheduler` count owner. Policy
selection retains issue-count, threshold, settings and current-organization order.
Current card/publication owners are selected at their original operation phases;
counts and child persistence may survive a later failure or cancellation. Existing
transition/publication services retain authority. Direct private embeddings migrate
to the focused owner; no facade forwarding/count alias remains. Migration:
`docs/architecture/CONTRACT_DELTA_ORCHESTRATOR_SCHEDULER_E2_2026-09-28.md`.

Acceptance requires actual request and file flows, unchanged readiness interpretation,
identical-input value parity, explicit missing-input refusal, captured-input behavior
through suspension, and retained workers under cancellation/timeout/shutdown. Installed
source binding, BT-1 through BT-5 and previous scoped guarantees remain required.
This contract does not establish full D acceptance, Linux clock repair, provider-backed
CAP acceptance, whole-plan completion or lane retirement.

Turn ops retains issue/default/review selection and dependency admission. The
focused turn workflow orders the existing review, preparation and result phases;
service construction selects current owners at those original phase boundaries.
Prepared-value normalization, stop decisions, card preparation, dispatch event,
success/failure handling and finally-close ordering remain. Private close lookup
at finalization stays distinct from the preparation service's earlier capture.
No effect, provider-cleanup or cancellation authority moves into this extraction.
Scope and proof: `docs/architecture/CONTRACT_DELTA_ORCHESTRATOR_TURN_PHASES_E2_2026-09-28.md`.
