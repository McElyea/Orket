# Nervous System v1 Implementation Plan (Action-Path MVP, Locked v5)

## Summary
Build a feature-flagged Nervous System v1 for `action.tool_call` proposals only, with deterministic admission/commit, approval queue, scoped per-action credential tokens, append-only governance ledger, outbound leak blocking, and OpenClaw JSONL subprocess live verification.

Execution status (2026-03-03):
1. Locked v1 slices implemented in repo (`orket/kernel/v1/*nervous_system*`, approval router integration, OpenClaw JSONL adapter).
2. Live verification completed via `python scripts/MidTier/run_nervous_system_live_evidence.py`.
3. Evidence artifact: `benchmarks/results/nervous_system_live_evidence.json`.

## Scope and Semantics
1. v1 handles action path only; no content arbitration.
2. `ACCEPT_TO_UNIFY` is retained for compatibility.
3. In v1, `ACCEPT_TO_UNIFY` means accepted to execute path; UnifyGate is not invoked.
4. v1 commit records action decision/result lineage, not content patch merge.
5. v1 commit does not mutate canonical state by default; it still returns `canonical_state_digest`.

## Canonical IDs and Time
1. `session_id` groups a run/session and is the per-session hash-chain unit.
2. `trace_id` identifies one end-to-end action lifecycle.
3. `request_id` is optional caller correlation.
4. Every ledger event must include `session_id` and `trace_id`; `request_id` is optional.
5. All `created_at`, `updated_at`, `expires_at`, `used_at`, and `resolved_at` fields are UTC ISO-8601 strings.
6. UTC timestamp format is normalized for all events/tokens to prevent timezone drift in replay/tests.
7. `GENESIS` is a fixed digest constant for new sessions.
8. Locked value: `GENESIS_STATE_DIGEST = "0000000000000000000000000000000000000000000000000000000000000000"`.

## Locked Reason Codes (v1)
1. `SCHEMA_INVALID`
2. `POLICY_FORBIDDEN`
3. `LEAK_DETECTED`
4. `SCOPE_VIOLATION`
5. `UNKNOWN_TOOL_PROFILE`
6. `APPROVAL_REQUIRED_DESTRUCTIVE`
7. `APPROVAL_REQUIRED_EXFIL`
8. `APPROVAL_REQUIRED_CREDENTIALED`
9. `TOKEN_INVALID`
10. `TOKEN_EXPIRED`
11. `TOKEN_REPLAY`
12. `RESULT_SCHEMA_INVALID`
13. `RESULT_LEAK_DETECTED`

Rules:
1. `AdmissionDecision.reason_codes` must be deterministic and ordered.
2. Ordering is stable by the locked list above.

## Kernel API Contracts
1. `POST /v1/kernel/projection-pack`
2. Input includes `session_id`, `trace_id`, optional `request_id`, `purpose="action_path"`, optional `canonical_state_digest`, tool context summary, policy context.
3. Output includes `projection_pack`, `projection_pack_digest`, `policy_digest`, `contract_digest`, `canonical_state_digest`.
4. If `canonical_state_digest` is omitted, kernel uses latest session head digest, else `GENESIS`.

5. `POST /v1/kernel/admit-proposal`
6. Input is `ProposalEnvelope`.
7. Output is `AdmissionDecision` plus `decision_digest`.

8. `POST /v1/kernel/commit-proposal`
9. Input includes `proposal_digest`, `admission_decision_digest`, optional `approval_id`, optional `execution_result_digest`, optional `sanitization_digest`.
10. Output includes `commit_event_digest`, `canonical_state_digest`, `status`.
11. Locked commit status enum:
12. `COMMITTED`
13. `REJECTED_PRECONDITION`
14. `REJECTED_POLICY`
15. `REJECTED_APPROVAL_MISSING`
16. `ERROR`
17. `ERROR` is only for internal failures (DB I/O, serialization, unexpected exceptions).
18. Validation/logic failures must map to explicit non-`ERROR` statuses.
19. Commit invariant: must fail if no prior matching `admission.decided` for exact `proposal_digest`.
20. Commit idempotency: same `(proposal_digest, admission_decision_digest, approval_id, execution_result_digest)` returns same `commit_event_digest` and status.
21. `commit.recorded` is emitted for all terminal commit outcomes (including rejections) to preserve deterministic lineage.
22. `action.result_validated` is emitted only when `action.executed` occurs.

21. `POST /v1/kernel/end-session`
22. Input includes `session_id` and optional reason.
23. Behavior appends `session.ended` event and invalidates all active session tokens.
24. Controlled shutdown must also write `session.ended` for active sessions.

## Approval API and State Machine
1. `GET /v1/approvals?status=&session_id=&request_id=&limit=`
2. `GET /v1/approvals/{approval_id}`
3. `POST /v1/approvals/{approval_id}/decision`
4. State transitions are `PENDING -> APPROVED | DENIED | APPROVED_WITH_EDITS | EXPIRED`.
5. Terminal states are `APPROVED`, `DENIED`, `EXPIRED`.
6. `APPROVED_WITH_EDITS` creates a new proposal digest and returns to admission, never direct execute.
7. Decision endpoint is idempotent for identical payloads.
8. Conflicting decision payloads return `409`.

## Ledger and Queue Model
1. Source of truth is append-only `governance_ledger_events`.
2. `pending_gate_requests` is a derived mutable queue/index cache rebuildable by replay.
3. Required rebuild helper is `rebuild_pending_approvals(session_id)`.

Ledger schema:
1. `id INTEGER PRIMARY KEY AUTOINCREMENT`
2. `event_digest TEXT UNIQUE NOT NULL`
3. `session_id TEXT NOT NULL`
4. `trace_id TEXT NOT NULL`
5. `event_type TEXT NOT NULL`
6. `event_json TEXT NOT NULL`
7. `prev_event_digest TEXT NULL`
8. `created_at TEXT NOT NULL` (UTC ISO-8601)

Indexes:
1. `(session_id, created_at)`
2. `(trace_id, created_at)`
3. `(event_type, created_at)`

Chain rules:
1. Hash chain is per session.
2. First event in session has `prev_event_digest=NULL`.
3. Later events must link to previous event digest in that session.
4. Insert computes digest and validates prior link in the same transaction.
5. Atomic session-head updates are enforced via session-head table.

Required v1 event types:
1. `projection.issued`
2. `proposal.received`
3. `admission.decided`
4. `approval.requested`
5. `approval.decided`
6. `credential.token_issued`
7. `credential.token_used`
8. `action.executed`
9. `action.result_validated`
10. `incident.detected`
11. `session.ended`
12. `commit.recorded`

## Credential Token Broker
1. Store hash only; never store raw token.
2. `token_hash = HMAC_SHA256(server_key, raw_token)`.
3. Tokens bind to `proposal_digest`, `admission_decision_digest`, `tool_name`, `tool_profile_digest`, `scope_json`, `scope_digest`, and optional `executor_instance_id`.
4. `scope_json` must be canonicalized using kernel canonicalization.
5. Binding check uses `scope_digest = digest(canonical_json(scope_json))`.
6. `tool_profile_digest = digest(canonical_json(tool_profile_definition))`.
7. Token use must match `tool_name`, `scope_digest`, and `proposal_digest`.
8. Invalidate token on use, expiry, denial, and `session.ended`.
9. Token timestamps (`created_at`, `expires_at`, `used_at`) are UTC ISO-8601.

## Deterministic Admission Precedence
1. Schema invalid -> `REJECT` (`SCHEMA_INVALID`).
2. Policy forbidden -> `REJECT` (`POLICY_FORBIDDEN`).
3. Leak detected -> `REJECT` (`LEAK_DETECTED`).
4. Scope violation -> `REJECT` (`SCOPE_VIOLATION`).
5. Unknown tool profile -> `NEEDS_APPROVAL` (`UNKNOWN_TOOL_PROFILE`).
6. Destructive rule -> `NEEDS_APPROVAL` (`APPROVAL_REQUIRED_DESTRUCTIVE`).
7. Exfil rule -> `NEEDS_APPROVAL` (`APPROVAL_REQUIRED_EXFIL`).
8. Credentialed rule -> `NEEDS_APPROVAL` (`APPROVAL_REQUIRED_CREDENTIALED`).
9. Otherwise -> `ACCEPT_TO_UNIFY` (execute-path accept in v1).

## Exfil and Leak Policy
1. Exfil-class means tool profile `exfil=true` or non-local target (domain/URL/remote endpoint), even if currently disabled.
2. Outbound/exfil leak detection enforces reject.
3. Local tool results returning to brain are sanitized and logged as incidents, or blocked if policy requires.
4. Minimum detectors include PEM/private-key markers, AWS key patterns, GitHub token patterns, `.env` known secret assignments, and US SSN regex.
5. Optional email/phone detectors remain policy-gated.

## Implementation Phases
1. Refactor prep for touched oversized modules.
2. Kernel endpoint/contracts implementation.
3. Ledger/session-head/rebuild implementation.
4. Risk/scope resolver with ordered reason codes.
5. Credential token broker with canonical digest bindings.
6. Action-path integration into execution flow.
7. Approval API + CLI/TUI + transition/idempotency enforcement.
8. OpenClaw JSONL subprocess adapter.
9. Leak detector/sanitizer integration.
10. Feature-flag rollout and docs.

## Live Integration Verification (Required)
1. Run real OpenClaw JSONL subprocess path end-to-end.
2. Prove blocked destructive action scenario.
3. Prove approval-required scenario (request, decision, execution).
4. Prove credentialed token issuance/usage scenario.
5. Write `benchmarks/results/nervous_system_live_evidence.json` including `session_id`, `trace_id`, optional `request_id`, `proposal_digest`, `admission_decision_digest`, `approval_id`, token hash/id hash, `policy_digest`, `tool_profile_digest`, and required event digests.
6. If live flow fails, capture exact failing step/error in `docs/projects/future/NervousSystem/LIVE_BLOCKERS.md`.

## Tests and Acceptance
1. Endpoint contract tests for new kernel and approval APIs.
2. Commit precondition and idempotency tests.
3. Commit status mapping tests (`ERROR` internal-only).
4. Approval state transition and `409` conflict tests.
5. Session-end token invalidation tests.
6. Ledger transactional chain and concurrent write tests.
7. Queue rebuild parity tests from ledger.
8. Admission precedence tests including scope/exfil branches.
9. Leak detector/sanitization tests.
10. Secret exposure scans across adapter traffic, ledger payloads, queue payloads, and returned tool results.
11. End-to-end integration tests for block -> approve -> token -> execute -> commit.
12. Live OpenClaw tests.

Acceptance criteria:
1. executed-outside-policy incidents = 0
2. outbound PII/credential leaks = 0
3. raw credential exposure in audited channels = 0
4. deterministic replay parity passes
5. live evidence artifact is complete and reproducible
6. feature flag off preserves current behavior

## Assumptions and Defaults
1. Action-path MVP only.
2. `kernel_api/v1` is extended.
3. OpenClaw-first via JSONL subprocess.
4. Deterministic governance only.
5. Append-only ledger with no purge in v1.
6. Pending approvals remain a derived cache, not source of truth.
7. Pre-resolved policy flags are temporary harness behavior and require `ORKET_ALLOW_PRE_RESOLVED_POLICY_FLAGS=true`.
8. Resolver rollout is gated by `ORKET_USE_TOOL_PROFILE_RESOLVER=true`; default mode is fail-closed when both flags are off.
