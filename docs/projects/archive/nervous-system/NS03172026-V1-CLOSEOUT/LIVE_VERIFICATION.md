# Nervous System v1 Live Verification

Date: 2026-03-17

Archive note: This verification record is preserved under `docs/projects/archive/nervous-system/NS03172026-V1-CLOSEOUT/` after the action-path v1 lane closed.

## Command
`python scripts/nervous_system/run_nervous_system_live_evidence.py`

## Integration Path
- Mode: `subprocess_jsonl`
- Path: `primary`
- Adapter command: `python tools/fake_openclaw_adapter_strict.py`
- Policy flag mode: `resolver_canonical` (`ORKET_USE_TOOL_PROFILE_RESOLVER=true`, pre-resolved flags off)
- Result: success

## Scenario Results
1. blocked_destructive
- admission decision: `REJECT`
- commit invoked: `true` (explicitly called to record enforcement path)
- commit status: `REJECTED_POLICY`
- `action.executed` and `action.result_validated` are absent by design for non-executed outcomes.

2. approval_required
- admission decision: `NEEDS_APPROVAL`
- approval status: `APPROVED`
- commit status: `COMMITTED`
- operator surfaces: approval queue rebuild consistent, ledger inspection present, replay parity present, audit `ok=true`

3. credentialed_token
- admission decision: `NEEDS_APPROVAL`
- approval status: `APPROVED`
- token issuance: success
- token consume: success
- commit status: `COMMITTED`

4. credentialed_token_replay
- admission decision: `NEEDS_APPROVAL`
- approval status: `APPROVED`
- first token consume: success
- replay consume: `TOKEN_REPLAY`
- commit status (replay execution): `REJECTED_POLICY`
- `credential.token_used` event count remains `1` (no second token use event)

Lineage rule used in this run:
- `commit.recorded` is emitted for all terminal outcomes, including rejected commits.

## Evidence Artifact
`benchmarks/results/nervous_system/nervous_system_live_evidence.json`

The artifact includes per-scenario `session_id`, `trace_id`, `request_id`, `proposal_digest`, `admission_decision_digest`, `approval_id` (where present), `token_id_hash` (hashed only), `policy_digest`, `tool_profile_digest`, optional `scope_digest`, explicit `admission_decision`, explicit `commit_status`, and `required_event_digests`.

For the approval-required scenario, the artifact also records operator-surface output for:

- approval queue inspection
- ledger inspection
- approval queue rebuild
- action-lifecycle replay
- action-lifecycle audit

HTTP route coverage for the same lifecycle is enforced in:
- `tests/interfaces/test_api_nervous_system_operator_surfaces.py`

Resolver parity coverage is enforced in tests with:
- `tests/kernel/v1/test_nervous_system_resolver_parity.py`
