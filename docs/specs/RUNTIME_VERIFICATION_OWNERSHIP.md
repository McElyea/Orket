# Runtime verification input and publication ownership

Status: Active contract
Last updated: 2026-09-27

## Scope

This contract covers `RuntimeVerifier.verify()` and
`RuntimeVerificationArtifactService.write()`, and fixture admission through
`FixtureVerificationService.verify()`. Card acceptance authority remains
in `CARD_COMPLETION_ACCEPTANCE_CONTRACT.md`; support-artifact roles and history
remain in `MINIMUM_AUDITABLE_RECORD_V1.md`. A successful support verifier is not
accepted card completion.

## Verification admission

Each `verify()` invocation detaches the verifier's nested issue and artifact
configuration and organization process rules before its first await. It binds a
relative workspace to the invocation directory and captures the selected command
environment at that same boundary. An omitted environment observes the current
environment once per invocation; an explicit empty environment stays empty.
Later caller mutation, environment rotation or directory changes cannot select
different command arguments, stdout assertions, deployment requirements or child
inputs for that invocation. Independent invocations retain independent snapshots.
The existing stateless command supervisor binds its cancellation-log workspace to
that same captured root; acquired process resources still belong to its `run()`.

Capture covers the standard configuration values consumed by verification, not
arbitrary trusted Python callbacks or mutable external filesystem contents.
Filesystem observation still occurs when its admitted operation executes.

Native metadata, traversal, syntax read/compile and command-directory resolution
use the existing owned worker. An admitted operation settles through repeated
cancellation and timeout before caller return; file handles close in that scope.
No new command is admitted after that interruption. A native failure while
draining interruption remains a failure and cannot become an ordinary verifier
result that admits later commands. Without interruption, the existing syntax and
read-error diagnostics remain unchanged.

Commands retain the existing process supervisor, finite deadlines, cwd admission,
bounded output, complete-capture checks and descendant cleanup contract. Native
file observation has no new forced-stop deadline. These operations do not provide
a filesystem snapshot or hostile-code containment.

## Fixture admission

Fixture verification captures its destination object, consumed scenario graph,
workspace/environment and selected time/identity provider methods before its first
await. Standard `IssueVerification` and `VerificationScenario` models are required.
Their consumed fields detach through the single pure built-in graph capture owner
in `core/contracts/value_capture.py`: exact strings, booleans, integers, finite
floats, null, lists, tuples and string-keyed dictionaries. Custom models/values,
cycles, excessive recursion and non-finite values refuse before native effects
with `E_FIXTURE_VERIFICATION_INPUT_UNSUPPORTED`; no copy/serializer hooks run.
The log-event wrapper retains its existing API and `E_LOG_EVENT_INPUT_UNSUPPORTED`.

The service's constructor-selected environment is copied per invocation; an
explicit empty environment remains empty. Relative workspace binds to invocation
cwd through the existing process-context capture. The stateless supervisor binds
its cancellation-log workspace to that same root. Provider handles are borrowed;
their internal mutable state and external filesystem contents are not frozen.

Owned metadata resolution and `is_file` use the existing `run_owned_thread` owner.
Repeated cancellation and timeout wait for settlement. Successful metadata after
interruption propagates cancellation, admits no child and publishes no scenario
changes. An OSError/ValueError during that drain escapes instead of becoming a
failed-result value. Previously handled cancellation does not reclassify a new
operation. Without new interruption, current missing-file, invalid-policy and
native admission error mapping remains unchanged.

The required security event is also an owned native publication. Success without
interruption rethrows the original security refusal. Interruption during successful
publication propagates caller cancellation (or the caller's elapsed timeout) after
settlement. Native publication failure takes precedence, including after interruption;
it is not converted into a supporting note or ordinary verification result. An
append may already exist when failure is reported. Lifetime-event retention and
command/container cleanup authority remain unchanged; events are not durable
recovery authority. Captured roots and fields apply to all these observations.

The command and fixture lifetime finalizers use the existing shared I/O owner
after the resource owner settles. Later caller cancellation cannot replace the
selected outcome; native publication failures retain their original identity,
including native cancellation and fatal failures. The command supervisor keeps
its existing expected-error-to-cause mapping; the fixture keeps its original
publication-failure precedence. Security publication retains the distinct normal
operation policy above. Contract and scoped proof:
`../architecture/CONTRACT_DELTA_REQUIRED_FINALIZERS_D_2026-09-28.md`.

The command and fixture lifetime finalizers use the existing shared I/O owner
after the resource owner settles. Later caller cancellation cannot replace the
selected outcome; native publication failures retain their original identity,
including native cancellation and fatal failures. The command supervisor keeps
its existing expected-error-to-cause mapping; the fixture keeps its original
publication-failure precedence. Security publication retains the distinct normal
operation policy above. Contract and scoped proof:
`../architecture/CONTRACT_DELTA_REQUIRED_FINALIZERS_D_2026-09-28.md`.

Both fixture and sandbox HTTP services require an explicit `utc_now` callable.
Each invocation samples once, requires an aware datetime and normalizes it to UTC;
naive/non-datetime values refuse with `E_VERIFICATION_TIME_REQUIRES_AWARE_DATETIME`.
Orchestration binds its selected turn clock before its first card await. Direct
embeddings supply the port. Captured scenario results replace the destination's
scenario sequence only after settled execution; concurrent edits are not merged.
No new `last_run`, scenario result or clean outcome follows cancellation or
unconfirmed cleanup. Native child effects already performed are not rolled back.

Fixture admission and explicit time are active additions for prospective checkpoint
0.6.113. Copied-source and current-source closing are recorded separately;
installed acceptance remains pending. Migration and scoped proof limits:
`../architecture/CONTRACT_DELTA_FIXTURE_INPUT_TIME_D_2026-09-27.md`.

## Support-artifact publication

`write()` captures its workspace and detached nested result/guard values before
waiting for filesystem work. One admitted publication owns path observation,
record/latest writes, index read/update/write and handle closure through the
existing shared I/O owner. Repeated cancellation or timeout waits for that
publication to settle; a publication failure remains visible even during
interruption. An interrupted caller can therefore observe completed artifacts.

Record and latest artifacts share the captured payload and existing JSON schemas,
record identities and relative history references. They retain
`artifact_authority=support_only` and `authored_output=false`. The index preserves
its existing sorting and same-record replacement semantics. Existing missing,
invalid or unreadable index handling remains tolerant and supplies empty history.

Publication is not a transaction across its three outputs. A failure can retain
an earlier record or latest file without a completed index, and concurrent writers
are not serialized by this contract. Inspect retained artifacts after failure or
interruption; absence of a return value does not establish absence of effects.
Resolved-path admission does not provide handle-bound protection against path
replacement. No success or rollback is inferred from supporting logs.

## Required controls

Keep the input/publication ownership integration cases alongside existing runtime
verifier, support-history, command-lifetime, shutdown and card-acceptance guards.
Controlled native holds use a declared 0.5-second independent SQLite response
bound; they prove responsiveness under injected latency, not natural filesystem
performance. Verify real child inputs, retained files and closed native handles.
Installed/native platform acceptance and provider-backed acceptance are separate
proof obligations; this contract does not itself report them as passing.
