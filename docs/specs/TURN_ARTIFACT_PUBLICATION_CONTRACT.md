# Turn artifact input and publication ownership

Last updated: 2026-09-24
Status: Implementation contract; acceptance and publication tracked in the architectural-truth plan
Owner: Orket Core

This contract covers turn observability and replay artifacts produced by the
existing TurnExecutor, TurnArtifactWriter, parser, prompt-budget and control-plane
routes. The architectural-truth plan owns execution status and proof. The matched
.101 opening demonstrates response-write lifetime and raw-input defects only.
Requirements below define the implementation; their proof status remains in the plan.

## One destination and the existing writer

One frozen `TurnArtifactDestination` carries the existing writer reference,
captured absolute workspace, session ID, issue ID, normalized role name, role ID
and turn index. Its output directory uses one shared path formula and the existing
`orket.naming.sanitize_name`; its control-plane run ID uses existing `run_id_for`.
Neither value is reconstructed from mutable context after suspension.

The public `TurnExecutor.execute_turn` boundary captures these values before
service selection or the execution-owner hold can await. The same destination
reaches prompt, model response, parser, validation/execution integration, local
checkpoint, control-plane snapshot, replay, protocol receipts and memory output.
Later changes to the caller's issue, role, context identity slots, writer workspace
or executor writer slot cannot redirect that invocation's admitted artifacts.

A separate frozen `TurnControlPlaneBinding` captures the existing dispatcher and
its control-plane service, namespace and resume/replay selections at that same
public boundary. The service whose execution owner is held remains the service
used for replay, checkpoints and dispatch. Later slot or namespace mutations do
not switch authorities. This binding creates no new service, lock or repository.

Every path-bearing writer method requires the destination and verifies that its
writer is that method's existing owner. There is no optional reconstruction,
mutable dispatcher-level destination cache or compatibility forwarding path.
Existing bound callback injection remains explicit; foreign-writer destinations
refuse. Pure hashing and non-path operations need no second destination authority.
Prompt previous-turn lookup uses the same path owner, not a copied directory formula.

Required destination fields do not remove existing entry semantics: preserve
the current session precondition, temporary unknown-session default, turn-index
default of zero, role normalization and blank-name sanitizer behavior. Do not
introduce unrelated earlier empty-ID or negative-turn refusals. Any lexical path
refusal is a separate intentional migration backed by the matched .101 path
opening. Sanitized session, issue and role tokens must be single lexical path
components: reject either separator, drive/root qualification, NUL, `.` and `..`.
Apply the same component rule to artifact filenames and sanitized tool/operation
filename tokens. Ordinary blank-name sanitizer defaults remain. This prevents
lexical redirection; it is not symlink or hostile-filesystem confinement.

Role ID is required explicitly as `str | None` and is metadata, not a path/run-ID
input. Ordinary turns capture the actual role ID. Retained approval identities
have a seat name but no role ID, so their destinations carry explicit `None`.
Recovery does not invent a role ID or emit memory traces from that absence.

## Capture boundaries and intentional output sinks

Capture only values consumed by a named operation. Unknown extension values,
callbacks, resource owners and frozen approval/completion records retain their
existing identity. This is not a deepcopy of the whole issue, role, context or
execution graph. The .101 admitted-command/result-sink contract remains in force.

MessageBuilder retains its .100 semantic input capture at builder entry. It also
receives the original destination for named identity fields in the issue header,
guard selector, execution-context issue/seat, blocked-issue membership, missing-read
events and compacted packet role. Non-identity prompt inputs still come from
builder entry. Original prompt metadata/layer dictionaries remain intentional
output sinks. Arbitrary middleware or custom raw prompt text is not rewritten to
enforce identity-like prose.

The captured initial message sequence used by the hash, budget and artifacts is
also forwarded to the first model call and used as the corrective prompt base.
Replacing or mutating the middleware's original list during publication cannot
substitute a different model input after the artifact/hash capture.

After `after_model` accepts or replaces a response, capture it once before the
first response write. A corrective response gets a fresh capture. Response text,
raw JSON and parsing consume that same capture. Dictionary responses remain the
whole raw dictionary; they are not reinterpreted as a nested `raw` envelope.
Non-dictionary raw values retain their artifact representation and the parser's
existing empty-dictionary behavior.

Render raw JSON before admitting the first response write, retaining current
formatting and `default=str`. Detach named native tool-call collections and the
consumed token/model/prompt/state/resume fields. Unknown opaque extension objects
remain borrowed; their identity must not be replaced by JSON roundtripping.
Unconsumed nested extension mutation is outside this capture guarantee. Preserve
strict, partial and native-fallback parsing policy, conversion order and diagnostics.
The intentional serialization-order change is explicit: an unrenderable raw
payload now refuses before the first text artifact, rather than after it.

Parser policy inputs are captured before its native operation: protocol enablement,
response/tool limits, hashes/versions, declared interfaces and required-action tools.
Parser identity and workspace come from the destination. It must not retain a
second mutable workspace or invoke a writer bound to a different destination.

## Operation-result and replay inputs

A persisted operation slot is missing only when its admitted content read observes
`FileNotFoundError`. Path construction or directory admission failure, unreadable
content, malformed JSON, a non-object value or an invalid record is present-invalid
and refuses under `E_OPERATION_ARTIFACT_INVALID`; it must not become a cache miss
that admits the toolbox. Path admission, content read, parsing and recognized error
conversion remain inside the existing owned native operation.

Every present operation record uses the shared strict validator. It requires exact
operation ID and tool name, equality of canonical JSON argument hashes, a dictionary
result and an exact 64-character lowercase hexadecimal digest equal to the canonical
result hash. Canonical comparison preserves JSON semantics: dictionary order is
irrelevant, persisted arrays match tuple inputs, and booleans do not equal numbers.
The accepted result is detached before a later await.

Policy, compatibility, workspace, gate, skill and approval checks retain their
existing order before cache selection. Ordinary governed operation-record and
legacy call-keyed hits additionally require their current durable control-plane
anchors. A miss in both caches proceeds through ordinary dispatch admission.

Embedded `TurnExecutor` protocol replay still performs model inference and parsing
to obtain a fresh proposal, then requires exact stored operation records and skips
toolbox execution. It is distinct from `orket protocol replay`, whose recorded-run
contract bypasses model inference and prompt construction. Neither route may use
the other route's name to claim a broader no-model or execution guarantee.

Compatibility-translated calls retain the existing parent-operation admission and
canonical hashing authority. This change adds no child-operation identity, second
serializer, cache filename migration or compatibility fallback.

## Admitted native work and document order

Use the existing owned-I/O/native-thread implementation. Repeated cancellation
and caller timeout retain admitted native work through completion and resource
closure. A native failure stays visible under that owner's existing precedence.
Clean cancellation prevents admission of the next document or later model/parser
stage. A retained late native failure instead enters the existing error handling,
which can publish failure traces as described below. An already completed document
or partial file may remain.

Existing snapshot-read classification is preserved: an absent, malformed or
unreadable snapshot returns the existing missing/malformed control-plane refusal.
The reader converts its recognized `OSError` inside the owned operation. Pending
cancellation therefore wins over that converted normal return; this route does
not promise propagation of the original read exception. Unconverted native faults
and publication failures retain their existing owned-I/O precedence.

Preserve these publication boundaries and order:

1. Response text, then raw JSON, as separately admitted writes.
2. Initial messages, then prompt layers, as separately admitted writes.
3. Prompt-budget usage, structure, previous-structure read and conditional diff
   remain one owned native batch in their existing order.
4. Parser diagnostics, parsed calls and summary remain one owned native batch.
5. Memory trace then retrieval trace remain one owned native batch.

Every batch receives captured/rendered inputs before worker admission. Native
directory creation, open, write/read and close belong to that same operation.
Do not insert an atomic-bundle, rollback, hard filesystem deadline, forced-thread
termination or durable-flush claim. Existing partial-prefix/recovery semantics stay
visible. A blocked or stuck native operation can delay cancellation indefinitely.

Prompt-budget refusal continues to publish its budget artifacts before returning
the refusal; it admits neither initial message artifacts nor model inference.
Corrective retries overwrite response/parser artifacts at the same destination
without rewriting the original messages/layers. Retain that mixed provenance.

## Prompt budget and optional token counters

At entry, capture the absolute policy path, stage, strict-tokenizer requirement,
ordered messages/partitions, prompt hash/version/count and destination. Capture
the selected bound counter once, preserving direct-client then provider precedence.
An empty bucket does not invoke a counter. Count total, protocol, tool-schema and
task buckets in the existing order; a refusal or interruption admits no later bucket.

The optional counter accepts existing integer/dictionary results and existing error
conversion. Await only results recognized by `asyncio.iscoroutine`; do not extend
the protocol to arbitrary awaitables. No in-tree production backend currently
implements this optional seam. Controlled counter tests therefore cannot establish
actual backend tokenizer equivalence or provider acceptance.

A single owned operation includes native callback execution, any returned coroutine
continuation, and count/error normalization. Preserve the existing conversion scope:
recognized callback/continuation errors are converted; normalization failures outside
that current catch remain failures. Do not expand dictionaries to arbitrary mappings.
Native callbacks run off the event
loop and are shielded and drained through the full operation. Known async callbacks
receive the existing one-cancellation/drain behavior. Recognized callback errors
are converted inside this operation, so a pending caller interruption wins over a
converted normal result. Unrecognized failures retain the owned-I/O failure
precedence. Policy-load and artifact failures are outside counter-error conversion.
Do not catch a late native callback failure outside the owner and accidentally
suppress cancellation, or discard an unawaited coroutine returned by native work.

## Clock, checkpoint and recovery order

The existing pipeline RuntimeInputService remains the clock owner. Bind its UTC
callback once and forward it explicitly through wiring, Orchestrator, TurnExecutor
and parser. No lower-level implicit clock, new clock service or construction-input
schema field is introduced. Parent/child pipelines retain the same input service.

A returned parsed turn samples time after all three parser artifacts finish,
inside the owned parser operation. A strict parse exception or artifact failure
samples no completion time. A returned partial-parse turn samples once. Retained
replay without an original response timestamp still uses `None`.

Checkpoint publication captures one timestamp and all consumed values before its
first await. The local checkpoint and any newly created snapshot/record reuse that
sample. An existing record retains its historical time. Preserve reentry validation,
local checkpoint write, begin-execution, lookup, new snapshot/record if absent,
and acceptance order. A local write failure prevents begin-execution; a later
snapshot failure can leave a run/attempt without checkpoint acceptance. No rollback
or automatic acceptance is implied by such a prefix.

Completed replay and pre-effect recovery use the captured destination for lookup
and validate retained snapshot identity before use. Approval callbacks publish
request rows, operator/control-plane targets and artifacts for that same identity.
The existing approval/checkpoint schemas and supported pre-effect ceiling remain.

Completed replay, pre-effect resume and approval continuation validate the full
persisted snapshot payload against the checkpoint's existing integrity reference
before consuming its tool plan. Formatting or dictionary order alone does not
change that canonical digest. In pre-effect resume, the existing recovery admission
and lineage lookup precede the snapshot read; an integrity refusal can therefore
retain the committed recovery prefix. It adds no rollback, repair or fresh attempt.

Tool-approval callbacks receive this required destination from dispatch. Request
rows and control-plane holds reuse its identity and one sample of the explicitly
supplied turn clock; gate mode and issue status retain context-builder capture.

Epic approval continuation captures its existing writer and absolute workspace
before the first repository await. Once retained child identities are available,
capture every child destination before later lock/repository awaits. Forward them
through claim/recovery and reject a reloaded identity mismatch. Do not reread the
mutable writer slot or workspace later, add another service workspace authority,
or cache a per-turn destination on a reusable service.

## Memory publication

Capture enabled/configuration inputs at invocation entry. Preserve admission order
when exposing the invocation's event sink: a refused execution owner does not
publish a newly allocated turn sink. Append to the original admitted event list,
even if a caller later replaces a context slot. Detach nested consumed event-row
values when appended; do not traverse arbitrary extension resources.

At terminal publication, freeze/render the consumed turn results, events and
retrieval payloads before the native batch. Ordinary completion, completed replay
and failure use the same capture/render and writer authorities. Require the actual
captured role ID for memory emission. Keep current formats, normalizations,
fingerprints and fallback event behavior.

Preserve the current failure route when success memory publication raises OSError:
the surrounding turn handler can append a failure event and attempt failure-memory
publication at the same destination, overwriting an earlier prefix. Do not silently
remove or reinterpret this retry/overwrite behavior as atomic publication. A late
native failure preserved while draining cancellation may enter this same recovery
route; it is not a clean-cancellation outcome. Success/replay or an early failure
helper inside the main try can reach at most one further failure publication.
A failure publication inside an exception handler is not retried: its error escapes.
No third attempt or retry of an earlier failed artifact is introduced.

## Acceptance and limits

Required proof includes matched opening counterexamples, real first/second write
and mkdir/read failures, caller cancel/timeout/repeated-cancel settlement, physical
readbacks and independent SQLite latency below the unchanged 0.5s bound. Composed
held-owner/provider cases must mutate identity, context, workspace and writer slots
and independently observe unchanged artifact/turn/checkpoint/tool/approval targets.
Recovery, foreign-writer and retained-identity mismatch controls fail closed.

Retain every failed and passing observation. Structural dependency/size/authority
checks, exact source/sdist/wheel/installed parity and prior behavioral identities
remain required. The canonical plan distinguishes live, structural and absent proof.
This contract does not admit a provider, workload, hostile-code boundary, Linux
clock result, full-suite coverage result or whole-lane completion.
