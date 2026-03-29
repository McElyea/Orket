# Contract Delta

## Summary
- Change title: ReviewRun answer-key score report framing, provenance, and weighted aggregate coherence
- Owner: Orket Core
- Date: 2026-03-29
- Affected contract(s): `scripts/reviewrun/score_answer_key.py` score report; workload-side score consumption in `scripts/workloads/code_review_probe_reporting.py`

## Delta
- Current behavior: review answer-key scoring already failed closed on drifted review-bundle authority markers and already emitted versioned score reports with required top-level `run_id`, but the shared validator still did not require top-level fixture/snapshot/policy provenance fields, still trusted aggregate totals inside the nested deterministic/model-assisted score blocks without proving they matched the issue rows they summarized, it could not prove model reasoning/fix subtotals against those rows because the emitted contract did not carry the weights used to compute them, and it could still accept a disabled model block that carried derived model activity.
- Proposed behavior: review answer-key scoring now requires non-empty top-level fixture/snapshot/policy provenance fields, requires the deterministic and model-assisted aggregate totals to stay aligned with the per-issue rows they summarize, emits explicit model reasoning/fix weights so the validator can prove reasoning/fix subtotals against those same rows, requires disabled model blocks to remain free of derived model activity, validates that stronger contract before returning, and workload-side code-review probe score consumers now fail closed if that score-report contract drifts at the nested block, aggregate, issue-row, or top-level provenance level.
- Why this break is required now: Workstream 1 is demoting review-local run-like read surfaces. Leaving answer-key scoring as internally inconsistent but structurally valid JSON would preserve another soft evidence surface beside the already-hardened review bundle and consistency-report seams.

## Migration Plan
1. Compatibility window: none for malformed score reports; truthful score payloads remain additive.
2. Migration steps:
   - require top-level fixture identity plus snapshot/policy digest provenance fields on emitted score reports
   - require deterministic/model-assisted summary blocks to keep the expected typed fields and aggregate totals aligned with the issue rows they summarize
   - emit explicit model reasoning/fix weights and require reasoning/fix subtotals to stay aligned with those same issue rows
   - require disabled model blocks to keep score and activity fields at zero
   - validate that stronger score-report contract again at workload-side score consumption
   - update Workstream 1 authority docs in the same change
3. Validation gates:
   - contract proof for score-report provenance and aggregate coherence
   - contract proof for workload-side score-consumer rejection of drifted score-report provenance or aggregates

## Rollback Plan
1. Rollback trigger: truthful answer-key score reports begin failing the new contract checks on the default path.
2. Rollback steps:
   - revert the score-report contract emission and validation in `scripts/reviewrun/score_answer_key.py`
   - revert workload-side score-report validation in `scripts/workloads/code_review_probe_reporting.py`
   - revert the aligned Workstream 1 authority wording
3. Data/state recovery notes: no migration is required; the change only rejects malformed score-report payloads.

## Versioning Decision
- Version bump type: additive fail-closed contract hardening
- Effective version/date: 2026-03-29
- Downstream impact: answer-key score consumers must now accept `reviewrun_answer_key_score_v1` payloads whose top-level fixture identity plus snapshot/policy digests remain present and non-empty, whose deterministic/model-assisted aggregate totals remain aligned with the per-issue rows they summarize, whose model reasoning/fix weights and reasoning/fix subtotals remain aligned with those same rows, and whose disabled model blocks keep activity fields at zero, and malformed score-report payloads now fail closed instead of being trusted through loose dict shape.





