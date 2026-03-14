Orket Protocol-Governed Agent Runtime Requirements (v5.1)

1. Purpose

Orket executes LLM-driven workflows deterministically and safely by treating the model as an untrusted proposal generator.

The runtime, not the model, enforces correctness through:

- strict protocol parsing
- deterministic validation
- tool execution under controlled environments
- append-only ledger events
- immutable receipts
- content-addressed artifact storage
- deterministic replay and crash recovery

The runtime must guarantee:

same inputs -> same validation -> same execution -> same receipts -> same artifacts

This document defines the complete runtime contract required to eliminate protocol ambiguity, prevent nondeterministic execution, and support large-scale workflows.

2. Problem Statement

LLM agents frequently fail to comply with structured tool protocols.

Observed failures include:

- `tool_calls: []`
- long reasoning dumps
- protocol speculation
- thousands of tokens for trivial tasks

Root cause:

If the protocol is ambiguous or interpretable, models begin reasoning about the protocol instead of executing the task.

This phenomenon is referred to as protocol curiosity.

The runtime must enforce mechanical compliance and must not rely on model discipline.

3. Goals

3.1 Deterministic execution

All executions must be reproducible from the ledger and artifacts.

3.2 Strict protocol

Only one valid response encoding exists.

3.3 Runtime authority

All enforcement occurs in runtime validators, not prompts.

3.4 Replay safety

Crashes and retries must never duplicate side effects.

3.5 Performance

The runtime must support:

- 100k+ steps per run
- parallel workers
- large artifact graphs

3.6 Protocols must be boring

Protocols must not invite interpretation.
They must be mechanical and validator-enforced.

4. Non-Goals

The runtime must not rely on:

- fuzzy parsing
- protocol explanation prompts
- model self-discipline
- implicit argument coercion
- automatic repair of invalid responses

5. Core Mental Model

`LLM -> proposal`
`runtime -> validate`
`runtime -> execute`
`runtime -> record ledger events`
`runtime -> generate receipts`
`runtime -> store artifacts`

The model proposes.
The runtime decides.

6. Definitions

Proposal
Structured JSON envelope describing requested tool actions.

Tool-mode
Runtime step requiring tool calls only.

Analysis-mode
Optional narrative step with no execution.

Receipt
Immutable record of validation and execution.

Ledger
Append-only event log describing run progression.

Artifact
Content-addressed immutable output produced during execution.

6.1 Hash Function

All cryptographic hashes referenced in this specification use SHA-256 unless explicitly stated otherwise.

`H(x) = SHA256(x)`

Digest strings must be encoded as lowercase hexadecimal.

6.2 Canonical JSON

`canonical_json(x)` MUST follow RFC 8785 (JSON Canonicalization Scheme, JCS) with the additional requirements below.

Required rules:

- UTF-8 encoding without BOM.
- Stable object key ordering per RFC 8785.
- Arrays preserved in original order.
- No insignificant whitespace.
- No Unicode normalization.
- Duplicate keys MUST be rejected before canonicalization.
- Non-finite numbers (`NaN`, `Infinity`, `-Infinity`) MUST be rejected.

Canonical JSON must be used when computing:

- `proposal_hash`
- `receipt_digest`
- all multi-field hash identifiers defined in this spec

6.3 Hash Input Framing

Hashes over multiple fields MUST use canonical tuple framing, not string concatenation.

Required form:

`H(canonical_json({"v":1,"kind":"<name>","fields":[...]}))`

Rules:

- `v` is a schema version for hash framing.
- `kind` is a stable domain separator (for example, `operation_id`).
- `fields` order is fixed by this specification.
- Implementations MUST NOT use `H(a + b + c)` style concatenation.

6.4 Proposal String Identity

Strings inside proposal envelopes must remain byte-identical.
Unicode normalization must not occur during parsing, validation, or hashing.

7. Locked Decisions

LD1 - Single canonical response envelope
Responses must parse as exactly one JSON object.

LD2 - One encoding for multi-tool turns
Tool calls appear only in `tool_calls[]`.

LD3 - Validator is the constitution
Runtime validators enforce protocol. Prompts must remain thin.

LD4 - Minimal retry messages
Retries contain only:

`INVALID_TURN <error_code>`
`Retry.`

LD5 - Response size limits mandatory
Runtime enforces:

- `max_model_tokens`
- `max_response_bytes`
- `max_tool_calls`

LD6 - No canonicalization of proposal keys
Tool names and argument keys must match exactly.

LD7 - Optional stable tool ordering
If `required_sequence` is defined, tool order must match exactly.

LD8 - Fail-fast validation
Validation stops at the first failure.

LD9 - No automatic repair
Invalid responses are rejected.

LD10 - Seat-aware tool cardinality
Single-shot required tools appear exactly once.
`read_file` may appear multiple times when needed to cover required read paths for the active seat.

LD11 - Receipts immutable
Receipts must never be modified after creation.

LD12 - Run ledger is append-only
Run ledger writes must be append-only and sequential.
Ledger appends must be atomic at the event record granularity.
Partial events must never exist.

Random updates, rewrites, deletions, or truncations of historical ledger entries are forbidden.

LD13 - Monotonic ledger sequence numbers
Each event includes `event_seq`.
Replay order is defined solely by `event_seq`.

LD14 - No per-step state files as source of truth
Run state derives exclusively from ledger replay.

LD15 - Content-addressed artifacts
Artifacts are stored by cryptographic digest.

LD16 - Artifact metadata immutable
Artifact metadata must never change after commit.

LD17 - Ledger and blob store separation
Ledger stores references to artifacts, not artifact bytes.

LD18 - Strictness scope split (proposal vs runtime records)
Model proposal envelopes are deep-strict.
Unknown keys must be rejected at all levels:

- envelope
- tool_calls
- args

Runtime-owned records may evolve through versioned schemas, including:

- ledger events
- receipts
- artifact metadata
- indexes
- metrics records

Older runtimes may ignore unknown fields only in runtime-owned records.

LD19 - Required ledger framing format
On-disk ledger format MUST use the required framing in Section 12.

LD20 - Determinism control surface is mandatory
Runtime MUST constrain and/or capture nondeterministic inputs as defined in Section 16.4 and Section 16.5.

LD21 - Lease and commit conflicts are deterministic
Multi-worker lease and commit conflicts MUST follow Section 26 semantics.

8. Canonical Response Protocol

8.1 Canonical envelope

```json
{
  "content": "",
  "tool_calls": [
    { "tool": "name", "args": {} }
  ]
}
```

Envelope keys must be exactly:

`{"content","tool_calls"}`

Tool call keys must be exactly:

`{"tool","args"}`

Responses must contain no characters outside the JSON object except leading/trailing ASCII whitespace as defined in Section 8.3, trimmed exactly once per Section 9.2.

Unknown keys are rejected per LD18.

8.2 Tool-mode invariants

- `content == ""`
- `len(tool_calls) > 0`

8.3 ASCII whitespace rule

Only the following whitespace may be trimmed:

- `0x20` SPACE
- `0x09` TAB
- `0x0A` LINE FEED
- `0x0D` CARRIAGE RETURN

All other whitespace is invalid.

8.4 Markdown fences forbidden

Responses containing code fences must be rejected.

8.5 Proposal primitive

The envelope represents a single proposal.
Future multi-proposal evaluation must reuse this format.

9. JSON Boundary Requirements

9.1 Pre-parse size check

If response size exceeds `max_response_bytes`, reject immediately.

9.2 Single trim pass

ASCII whitespace trimming occurs exactly once.

9.3 Duplicate key rejection

Duplicate JSON keys must cause rejection.

If the parser cannot detect duplicates, the runtime must treat the response as `E_PARSE_JSON`.

9.4 No parser coercion

Type coercion is forbidden.

Example:

`"5" -> 5`

9.5 Proposal parser determinism

Given identical response bytes, parser version, and protocol version, parsing must yield the same parse tree or the same parse error code.

10. Deterministic Validator Pipeline

Validation order (fail-fast):

1. Parse JSON.
2. Reject duplicate keys.
3. Envelope strictness.
4. Mode gate.
5. Tool-call shape validation.
6. Tool schema validation.
7. Required tool enforcement.
8. Tool cardinality and read-path coverage check.
9. Workspace constraints.
10. Response caps.

10.1 Validator determinism invariant

Given identical:

- proposal envelope
- validator_version
- protocol_hash
- tool_schema_hash

The validator must produce the same validation outcome and `error_code`.

10.2 Workspace constraints

Filesystem safety rules must be enforced.

Examples:

- writes must occur within workspace
- path traversal forbidden
- absolute paths outside workspace rejected
- symlink escapes prevented

Failure code:

`E_WORKSPACE_CONSTRAINT:<detail>`

11. Retry Policy

Retries must be deterministic and minimal.

Example:

`INVALID_TURN E_MISSING_REQUIRED_TOOL:update_issue_status`
`Retry.`

Retry messages must be less than 128 bytes.

12. Ledger Record Framing

12.1 Required on-disk framing (LPJ-C32 v1)

Every ledger record MUST use this exact format:

`uint32_be payload_len | payload_bytes | uint32_be crc32c(payload_bytes)`

Rules:

- `payload_bytes` is a UTF-8 JSON object (no BOM).
- `payload_len` is the byte length of `payload_bytes`.
- `payload_len` MUST be <= 4 MiB.
- `crc32c` is Castagnoli CRC-32C over `payload_bytes`.

12.2 Truncation and corruption handling

- If EOF occurs mid-record at tail, treat as end-of-log and ignore the partial tail.
- If checksum mismatch occurs for any fully length-addressable record, fail replay with `E_LEDGER_CORRUPT`.
- If `event_seq` is non-unique or non-monotonic, fail replay with `E_LEDGER_SEQ`.

12.3 Ledger ordering invariant

Event ordering is defined exclusively by `event_seq`.
Timestamps must not determine execution ordering during replay.

13. Two-Channel Prompting

Protocol channel

System message containing protocol rules.
Must remain byte-identical across the run.

Task channel

Per-step instructions and retry messages.

14. Response Size Controls

Recommended defaults:

- `max_model_tokens_tool_mode = 512`
- `max_response_bytes = 8192`
- `max_tool_calls = 8`

15. Receipts

Receipts record:

- `run_id`
- `step_id`
- `proposal_hash`
- `validator_version`
- `protocol_hash`
- `tool_schema_hash`
- `execution_results`
- `artifact_digests`
- `retry_count`
- `validator_duration_ms`

Reserved governance fields:

- `proposal_set_id`
- `proposal_source`
- `decision`
- `decision_reason_code`

15.1 Receipt digest

`receipt_digest = H(canonical_json(receipt))`

Excluded from digest:

- storage offsets
- filesystem metadata
- external timestamps

15.2 Proposal hash

`proposal_hash = H(canonical_json(proposal_envelope))`

15.3 Execution capsule

Receipts must include:

- `executor_image_digest`
- `toolchain_version_set`
- `os_arch`
- `network_mode`
- `clock_mode`
- `timezone`
- `locale`
- `env_allowlist_hash`

Purpose:

- diagnose nondeterminism
- explain replay differences

16. Deterministic Tool Execution

16.1 Operation guards

`operation_id = H(canonical_json({"v":1,"kind":"operation_id","fields":[run_id,step_id,tool_index]}))`

Duplicate operations reuse stored results.

16.2 Execution order invariant

Tools execute exactly in `tool_calls` order.

16.3 Validation-before-execution invariant

All tools must be validated before execution begins.
Validation and execution must not be interleaved.

16.4 Determinism control surface

Runtime MUST constrain and/or capture all nondeterministic inputs used by tools.

Minimum required controls:

- Time: default `timezone=UTC`; wall-clock reads in deterministic replay MUST use recorded values.
- Locale: enforce fixed locale (for example, `C.UTF-8`) for deterministic text and collation behavior.
- Environment: pass an explicit allowlist of environment variables; hash the allowlist into execution capsule.
- Filesystem traversal: directory iteration consumed by runtime logic MUST be byte-lexicographically sorted.
- Process cwd: fixed per tool execution and included in runtime config hash.
- RNG: tool-visible random source MUST derive from `step_seed`.

16.5 Network determinism

- Default `network_mode` is `off`.
- If network is enabled, allowed destinations MUST be explicitly declared.
- First-run request/response payloads used for tool decisions MUST be captured as artifacts.
- Deterministic replay mode MUST not perform outbound network calls; it MUST replay from captured artifacts.

17. Decision Governance

Receipts record decision context including:

- `protocol_hash`
- `task_prompt_hash`
- `validator_version`
- `workspace_digest`

Replay modes:

- full replay
- deterministic replay
- audit replay

18. Artifact-Mediated Coordination

Agents communicate through artifacts rather than chat.

Examples:

- `plan.json`
- `proposal.json`
- `critique.json`
- `decision.json`
- `patch.diff`

Each artifact has schema and transition rules.

19. Acceptance Criteria

Functional:

- tool-mode rejects narrative
- unknown keys rejected
- seat-aware tool cardinality enforced

Determinism:

- validator fail-fast
- replay reproduces identical step states
- ledger replay reconstructs identical run state

Performance:

- token caps enforced

20. Rollout Plan

Compat phase

Observe violations.

Enforce phase

Reject invalid responses.

21. Risks

Strict protocol may increase retries.

Mitigation:

- tighter token caps
- stronger models for tool steps

22. Run State Manager (RSM)

RSM responsibilities:

- step scheduling
- state transitions
- retry orchestration
- dependency resolution
- crash recovery
- replay

23. Artifact Storage Model

Artifacts stored in a content-addressed blob store.

Example layout:

`artifacts/blobs/sha256/ab/cd/<digest>`

Write procedure:

- write temp
- verify digest
- commit
- append reference

Artifact immutability invariant

Once a blob with a given digest exists, its contents must never change.

If the runtime encounters an existing digest, it must verify stored bytes rather than overwriting the blob.

Artifact digests are computed from raw artifact bytes only.
Filesystem metadata must not influence the digest.

24. Receipt Storage Model

Receipts stored in append-only log.

Example:

`runs/<run_id>/`
`  events.log`
`  receipts.log`

24.1 Receipt sequence numbering

Each receipt includes `receipt_seq`.

Replay order:

`receipt_seq` ascending

24.2 Cross-link requirement

Receipts and ledger events must be cross-linkable.

Receipts include:

- `event_seq_range`

Ledger events include:

- `receipt_digest` or `receipt_seq`

25. Deterministic Randomness

Recorded values:

- `run_seed`
- `step_seed`

Required derivation:

`step_seed = H(canonical_json({"v":1,"kind":"step_seed","fields":[run_seed,run_id,step_id]}))`

26. Multi-Worker Coordination

One RSM coordinator per run.

Workers produce:

- proposals
- execution results

RSM commits state transitions.

26.1 Lease exclusivity

Only one active lease exists for `(run_id,step_id)`.

Lease record fields:

- `lease_epoch`
- `lease_holder`
- `lease_expires_mono_ms`
- `lease_granted_event_seq`

26.2 Lease renewal and expiry semantics

- Lease grant/renew MUST be committed by coordinator using compare-and-swap on `lease_epoch`.
- Renew succeeds only if expected `lease_epoch` matches latest committed value.
- On expiry or CAS failure, worker MUST stop execution and report `E_LEASE_EXPIRED`.
- A worker that loses lease MUST NOT commit results.

26.3 Duplicate execution and commit race semantics

- `operation_id` remains authoritative idempotency key.
- If two results race for the same `operation_id`, the first committed `event_seq` wins.
- Later conflicting commits for the same `operation_id` MUST be rejected with `E_DUPLICATE_OPERATION` and linked to the winning record.

27. Observability

Metrics include:

- retry counts
- validation failures
- execution latency
- artifact sizes

Audit logs provide summaries.

28. Security Isolation

Tools must run in restricted environments.

Examples:

- container
- microVM
- sandbox runtime

Resource limits:

- CPU
- memory
- disk
- network

Secrets must use short-lived credentials.

29. Protocol Versioning

Runtime records:

- `protocol_version`
- `protocol_hash`
- `validator_version`

Breaking changes require version bumps.

30. Upgrade Strategy

Forward compatibility rules:

- new fields optional
- older runtimes may ignore unknown runtime fields
- proposal envelopes remain deep-strict

Breaking changes require protocol version increments.

31. Determinism Testing Infrastructure

A determinism harness must repeatedly execute workloads and verify:

- identical ledger
- identical receipts
- identical artifacts

Hidden nondeterminism must be detected before production deployment.

Final Architecture (Informative)

`LLM`
`  -> proposal protocol (deep strict)`
`  -> validator`
`  -> Run State Manager`
`  -> append-only event ledger`
`  -> tool executor`
`  -> immutable receipts`
`  -> content-addressed artifact store`

Deterministic replay depends on:

- `event_seq`
- `receipt_seq`
- `proposal_hash`
- `artifact_digest`
- `execution capsule`
- seed derivation
