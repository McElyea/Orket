# Completion prompt and governed guard rejection delta

## Summary

- Change title: Align guard proposals with retained acceptance and the governed envelope.
- Owner: Orket Core.
- Date: 2026-09-13.
- Affected contracts: `docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md`;
  existing governed tool-mode envelope in
  `docs/specs/PROTOCOL_GOVERNED_RUNTIME_CONTRACT.md`.

## Delta

- Current behavior: A guard prompt interpreted legacy verifier success as a
  reason to choose `done`, including empty and syntax-only support checks.
  Rejection guidance requested a second JSON object, but governed turns require
  one envelope with empty content. Validators and post-dispatch handling searched
  only text, making a valid governed blocked review impossible.
- Proposed behavior: Both prompt formats project the application acceptance
  decision, criteria, references and diagnostics. A blocked status call carries
  `args.guard_review` with typed rationale, violations and remediation actions.
  One application reader supplies both consumers. Malformed present metadata
  does not fall back to prose; multiple blocked decisions have no accepted payload.
- Why this break is required now: BT-3 requires actionable insufficient-evidence
  decisions without granting completion from model narration or support checks.
  The final persistence gate already requires independently verified acceptance;
  guard guidance and rejection now conform to that boundary.

## Migration Plan

1. Compatibility window: Existing non-governed text extraction remains supported;
   no new compatibility shim is added. Governed envelope keys and empty-content
   semantics stay as defined. New metadata is nested in existing tool arguments.
2. Migration steps: Update initial and corrective guidance together. Consume the
   actual turn in post-dispatch handling and remove duplicate JSON scanners.
   No database rewrite, historical receipt upgrade or model-evidence admission.
3. Validation gates: Retain failing prompt and governed rejection reproductions;
   exercise real SQLite persistence for valid and invalid structured metadata;
   exercise the engine through guard events and published unsuccessful outcome.
   Run legacy regressions and whole BT-3 source, installed and provider acceptance.
   Results and outstanding gates belong in the architectural-truth plan.

## Rollback Plan

1. Rollback trigger: Rejection diagnostics fail to reach the correct bound turn
   or accepted-completion authority becomes weaker.
2. Rollback steps: Restore the preceding runtime candidate and disclose that
   governed guard rejection is unavailable. Do not restore success claims based
   on support-only verification as an accepted completion behavior.
3. Data/state recovery notes: Keep existing histories, proposals and receipts.
   A blocked card is not a completed objective. Reevaluate current bindings on any
   later completion attempt using the existing application authority.

## Versioning Decision

- Version bump type: Patch candidate for the existing 0.6.x line; no release made.
- Effective version/date: Worktree implementation dated 2026-09-13.
- Downstream impact: Guard models use one structured payload in tool arguments.
  Prompt consumers receive fuller acceptance context. No new completion permission.
