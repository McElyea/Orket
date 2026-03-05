# Nervous System v1 Live Verification

Date: 2026-03-03

## Command
`python scripts/nervous_system/run_nervous_system_live_evidence.py`

## Integration Path
- Mode: `subprocess_jsonl`
- Path: `primary`
- Adapter command: `python tools/fake_openclaw_adapter_strict.py`
- Policy flag mode: `pre_resolved_flags` (`ORKET_ALLOW_PRE_RESOLVED_POLICY_FLAGS=true`, resolver off)
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

Resolver parity coverage is enforced in tests with:
- `tests/kernel/v1/test_nervous_system_resolver_parity.py`
