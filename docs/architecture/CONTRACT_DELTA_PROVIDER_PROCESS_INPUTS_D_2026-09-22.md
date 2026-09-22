# Provider and shared command input capture

Owner: Codex for Orket Core
Date: 2026-09-22
Status: Scoped implementation contract; acceptance remains in the canonical plan

## Delta

Provider policy already captures environment, but native CLI calls currently use
worker-time environment and cwd. Relative GGUF roots can change after HTTP awaits.
The shared command runner also passes borrowed arguments, environment and batch
input to a later transport task. Ten real process/HTTP/file controls fail on source
and the exact installed v0.6.89 wheel; original observations remain retained.

Capture one immutable environment and absolute lexical directory at public provider
entry and pass them through listing, loading and nested inventory. The shared
command owner freezes its borrowed inputs before scheduling transport, including
batch bytes and JSONL frames. Its private supervisor receives the captured directory
and environment. Preserve the existing OS lifetime owner, deadlines, output bounds,
partial results, model-selection/quarantine policy and observed-load requirements.

Durable authority: `docs/specs/PROVIDER_GOVERNANCE_COMMAND_OWNERSHIP.md` and
`docs/specs/VERIFICATION_PROCESS_LIFETIME_CONTRACT.md`. This does not freeze filesystem
or executable contents, establish actual inference, change HTTP proxy policy or
complete D/E/CAP. No compatibility shim or hidden ambient fallback is added.

## Migration and validation

The intended pre-1.0 patch checkpoint is 0.6.90. Provider and native inventory APIs
accept explicit environment/cwd inputs; callers without them retain invocation-time
defaults. Nested calls propagate captured values. Drive-relative paths now fail
explicitly because their meaning depends on hidden process state. Migrate strict
test wrappers to forward inputs while retaining every existing behavior assertion.
Synchronous public wrappers capture before the coroutine bridge too; two additional
real CLI controls expose that gap after the initial async repairs. The existing
607-line provider-target module grows by eleven lines for required signatures and
propagation. This is a scoped correctness exception under the contributor size
rule; the oversized module remains decomposition debt, not a clean size baseline.

Validate actual commands and model-state files, held HTTP/relative GGUF discovery,
mutated command inputs and private-supervisor context, plus existing cancellation,
timeout, responsiveness and installed-package controls. Synthetic invocation checks
alone are insufficient. Actual local inventory observations are separate from
fixture tests and cannot establish model inference or daemon-side rollback.

## Rollback

Any failed acceptance blocks publication. Revert code and authority together and
repeat affected proof; preserve failed observations. Process cleanup and code
rollback cannot reverse accepted model loads or other external effects. The lane
remains active until implementation, acceptance and explicit retirement criteria hold.
