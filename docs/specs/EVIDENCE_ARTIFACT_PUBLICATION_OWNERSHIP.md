# Evidence artifact publication ownership

Status: Active
Last updated: 2026-09-28
Owner: Orket Core application services
Related: [Sandbox event publication](SANDBOX_EVENT_PUBLICATION_OWNERSHIP.md),
[Outward run authority](OUTWARD_RUN_AUTHORITY.md),
[Outward run admission](OUTWARD_RUN_ADMISSION.md)

This contract scopes native filesystem lifetime and admitted inputs for
`SandboxTerminalEvidenceService.export`, `write_model_evidence`, and
`verify_model_evidence`. It does not grant terminal, proposal, authorization or
recovery authority to these files.

## Admission and lifetime

1. The public operation selects its root, references and required payload values
   before its first await. Mutable nested values needed after admission must not
   remain borrowed from the caller. Relative I/O roots bind lexically to admission
   cwd through the existing file-root capture helper; real resolution stays in
   the owned native attempt. Normal Path inputs are assumed.
2. One `run_owned_io(..., preserve_failure=True)` boundary retains the complete
   admitted publication or verification operation. The caller's cancellation,
   including repeated cancellation and an owning timeout, cannot complete the
   call before its admitted native mkdir, metadata, open, read/write, close and
   digest work settles.
3. A native operation failure after interruption remains the operation's failure.
   A successful retained attempt followed by caller interruption still raises
   cancellation; callers must not infer successful result publication merely
   because a file is now present.
4. Filesystem or process death can leave partial effects. This is neither a
   transaction across files nor crash-atomic publication. Retention does not
   forcibly stop a native thread, make blocked native I/O promptly cancellable,
   or establish protection from direct cancellation of private owner tasks.

## Sandbox terminal evidence

The selected document is fully rendered to immutable JSON text before yielding;
no additional payload-copy hook is invoked. The digest-named destination
and the JSON content must represent the same admitted nested payload. Existing
SHA-256 naming, terminal-reason prefix, JSON formatting, native text newline
behavior, overwrite mode and returned reference spelling are retained. Actual
relative-path writes use the captured root even if cwd later changes.

The retained attempt includes parent creation and the complete file context.
`SandboxTerminalOutcomeService` may record required evidence and terminal truth
only after export returns successfully. An interrupted export may leave a closed
complete file, while the terminal row remains unchanged. A failed export may
leave a partial file; neither outcome adds an implicit cleanup or retry authority.

Constructor-time path setup in `resolve_sandbox_terminal_evidence_root` is outside
this export contract. Relative returned references retain their existing spelling;
callers interpreting those references still need their established root binding.
No new containment policy or handle-bound defense against hostile replacement is
introduced.

## Outward model evidence

The public writer captures rendered payload values before native admission. It
reads response/model/tool metadata at that boundary and detaches nested values.
Path resolution and final invocation-reference assignment belong to the retained
operation. Redaction, payload schemas, filename rules and digest material remain
the existing canonical definitions.

Publication preserves this order: prompt, response, proposal extraction, model
invocation. A legacy layout writes each turn file followed by its legacy alias;
an explicit admission scope writes only turn files with exclusive creation. Only
after every file context closes does the writer read the four turn files, compute
their digests and return evidence references. No implicit resealing, replacement
of an exclusive scope, deletion of partial files or provider redispatch is added.

Verification captures all four ref/digest pairs before yielding. It retains root
and reference resolution and each read/close through the existing required/scope/
unavailable/digest refusals. Changing a caller's evidence mapping mid-read cannot
substitute later reference pairs. This does not snapshot the filesystem across
reads, authenticate the producer, or prevent concurrent external file mutation.

The existing model-tool-call caller cannot publish its return value or advance
its ordinary client-close ordering past an unsettled evidence operation. Native
file proof with supplied model output is not provider execution proof. The
admission service's separate `validate_policy` worker and store transactions stay
outside this contract.

## Acceptance controls

The integration controls use real local files and SQLite, with held native
mkdir/open/write/read/close operations, repeated cancellation, timeout, combined
native failure, nested-input and cwd mutation, digest/refusal controls, legacy
alias parity, exclusive-scope partial-effect preservation, terminal row ordering
and model caller/client-close ordering. Timeout controls observe the actual
supplied task's deadline cancellation before releasing the held native operation.

The original source opening observed 37 failures and 8 passes across 45 evidence
cases. One timeout pass did not establish interruption before native release and
is not retention proof. The corrected timeout-only opening observed 14 failures
at the ownership assertion, each after exactly one observed deadline cancellation;
all 5,504 bound source inputs were unchanged. Original observations are retained.
The implementation is applied on the development candidate after 0.6.114. All 45
native closing controls and selected existing guards pass in the combined 512-case
Windows Python 3.11 run, with 5,509 inputs unchanged. These opening failures
are counterexamples, not proof that the implemented correction passes.
