# Runtime verification input and publication ownership

Status: Active contract
Last updated: 2026-09-27

## Scope

This contract covers `RuntimeVerifier.verify()` and
`RuntimeVerificationArtifactService.write()`. Card acceptance authority remains
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
