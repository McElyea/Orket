# Contract Delta

## Summary
- Change title: Governed turn-tool checkpoint resumability contract
- Owner: Orket Core
- Date: 2026-03-24
- Affected contract(s): `orket/application/workflows/turn_executor_control_plane.py`; `orket/application/workflows/turn_executor_resume_replay.py`; `orket/application/workflows/turn_executor_completed_replay.py`; governed turn-tool checkpoint snapshot metadata; governed turn-tool recovery-decision publication

## Delta
- Current behavior: new governed turn-tool checkpoints were published as `resume_new_attempt_from_checkpoint`, and safe pre-effect `resume_mode` recovery interrupted attempt 1, created attempt 2, and continued on the replacement attempt.
- Proposed behavior: new governed turn-tool checkpoints are now published as `resume_same_attempt`, and safe pre-effect `resume_mode` continues on the current attempt after publishing a same-attempt `resume_from_checkpoint` recovery decision. Replay and recovery helpers still consume older governed `resume_new_attempt_from_checkpoint` lineage truthfully when those records already exist.
- Why this break is required now: the governed turn lane already had immutable pre-effect checkpoint truth and snapshot-backed replay, so continuing to force replacement-attempt recovery was authority drift rather than a real safety requirement. Closing the lane requires the live path to use the narrower same-attempt boundary it can now verify.

## Migration Plan
1. Compatibility window: transitional; new governed checkpoints publish `resume_same_attempt`, while replay and recovery still accept older governed `resume_new_attempt_from_checkpoint` records.
2. Migration steps:
   - publish same-attempt checkpoint snapshot semantics on new governed turns
   - publish same-attempt `resume_from_checkpoint` decisions for safe pre-effect governed `resume_mode`
   - keep completed replay and resume helpers compatible with older governed new-attempt lineage
3. Validation gates:
   - governed turn integration proof for same-attempt resume before model execution
   - governed turn closeout proof for dirty same-attempt resume fail-closed behavior
   - governed completed replay proof for accepted checkpoint plus immutable snapshot alignment

## Rollback Plan
1. Rollback trigger: same-attempt governed resume produces stale-attempt writes, duplicate tool execution, or broken checkpoint lineage on the default execution path.
2. Rollback steps:
   - switch governed checkpoint publication back to `resume_new_attempt_from_checkpoint`
   - restore replacement-attempt bootstrap in governed pre-effect `resume_mode`
   - leave transition compatibility for older same-attempt records in place only if rollback stops at new publication semantics
3. Data/state recovery notes: existing governed checkpoint and recovery records remain durable evidence. Older new-attempt lineage remains valid, and same-attempt records can be left as historical truth even if new publication reverts.

## Versioning Decision
- Version bump type: additive contract realignment with fail-closed governed runtime behavior
- Effective version/date: 2026-03-24
- Downstream impact: governed turn replay and resume consumers must accept `resume_same_attempt` on new checkpoint snapshots; code that assumed unfinished governed `resume_mode` always creates attempt 2 must stop making that assumption
