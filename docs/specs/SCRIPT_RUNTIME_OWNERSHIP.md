# Script runtime and replay observation ownership

Last updated: 2026-09-22
Status: Active implementation contract since 0.6.83, extended in 0.6.84; scoped proof belongs to the architectural-truth plan

ProductFlow command scopes own engine construction, execution and cleanup on one
event loop. Construction runs through the existing owned native worker. An acquired
engine closes before the command returns or publishes its final result, including
missing-run refusal and operation failure. Cleanup remains owned through repeated
cancellation; cleanup failure prevents a successful command return. The witness
campaign keeps execution and bundle collection on the same loop and closes that
engine before publishing the collected campaign outputs. Borrowed-engine operations
leave cleanup to their explicit caller.

ProductFlow's controlled fixture supplies the current immutable seat-policy input
and a canonical artifact acceptance definition for the exact approved output.
Completion still requires real persisted evidence. Witness resource observation
selects the latest retained record matching the accepted checkpoint's dependent
lease, rather than borrowing a later turn's namespace record. Missing matching
history refuses bundle construction. Existing witness verifiers remain unchanged.
Campaign acceptance still requires repeated equivalent runs; one run is insufficient.

Replay audit reads use the existing artifact diagnostics service directly, without
constructing a runtime or creating runtime databases. Diagnostics remain
observability-only, not canonical replay-verdict authority. The native observation
method refuses an event-loop thread before filesystem effects with
`E_REPLAY_OBSERVATION_REQUIRES_ASYNC_OWNER`. Async audit owns its worker until the
read settles, including repeated cancellation, timeout and read failure. The selected
workspace is made absolute before worker admission and resolved within that worker.
Read failures remain visible and cannot become empty replay success.

The default audit provider is an owned resource from construction through response
and cleanup. Cancellation cannot abandon transport close. An injected replay callable
owns its own resources; its result does not establish actual inference. Existing
report schemas, comparison rules and command exit mappings remain unchanged.

This is lifetime ownership, not rollback, crash atomicity, hostile-path confinement,
cross-process fencing or a new deadline guarantee. Existing test/command deadlines
remain unchanged. Required proof includes actual artifact and SQLite observations,
real engine cleanup, controlled HTTP transport lifetime, interruption and visible
cleanup failures. Linux clocks, full async/effect inventories, remaining input owners,
real-model acceptance, E/CAP and explicit user lane acceptance remain open.

The packet-1, packet-2 repair and artifact-provenance governance recorders are native
commands. They refuse an active event loop before environment, temporary-directory,
provider-hook or alias effects with `E_GOVERNANCE_PROOF_REQUIRES_NATIVE_CONTEXT`.
Each private async proof scope acquires its engine through `OrchestrationEngine.open`
and retains construction, execution and cleanup on the command loop before returning.
An operation refusal remains visible through interruption during cleanup; cleanup
failure takes precedence and cannot produce a successful proof. Existing payload
builders, runtime-success gates and summary validation remain unchanged.

Packet 1 restores environment overrides even if alias cleanup fails. It removes an
alias only after this invocation successfully created it; an alias already present
at admission remains untouched. A nonzero removal result raises instead of silently
succeeding. This process-local ownership does not fence other alias writers or resolve
an ambiguous interrupted copy. Child-process interruption supervision remains open.
Simulated alias command responses are contract proof only. Actual Ollama fallback
acceptance still requires the real service, model and CLI; another provider cannot
substitute for it.
