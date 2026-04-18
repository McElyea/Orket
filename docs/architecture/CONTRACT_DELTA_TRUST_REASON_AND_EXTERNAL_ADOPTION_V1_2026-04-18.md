# Contract Delta: Trust Reason And External Adoption v1

## Summary
- Change title: Introduce a bounded external trust/publication contract for the shipped trusted repo change proof slice
- Owner: Orket Core
- Date: 2026-04-18
- Affected contract(s): `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md`, `README.md`, `docs/README.md`, `CURRENT_AUTHORITY.md`

## Delta
- Current behavior: Public repo docs stay narrowly operational and proof artifacts exist, but there is no durable contract defining the current external trust reason, evaluator path, allowed claims, or publication boundary for the shipped proof slice.
- Proposed behavior: Add one durable contract and one evaluator guide that bound public proof-backed trust wording to `trusted_repo_config_change_v1`, cap truthful claims at `verdict_deterministic`, require replay/text-determinism disclaimers, require proof-only and fixture-bounded wording, and point evaluators to the shipped witness bundle, campaign report, and offline verifier report.
- Why this break is required now: The proof slice is already implemented. Without a durable publication boundary, README or future public wording can drift into overclaiming or reuse the proof slice as evidence for broader workflow trust.

## Migration Plan
1. Compatibility window: No compatibility shim. This is a documentation and authority extraction change.
2. Migration steps:
   1. add `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md`
   2. add `docs/guides/TRUSTED_REPO_CHANGE_PROOF_GUIDE.md`
   3. update README, docs index, and current authority to reference the bounded trust surface
3. Validation gates:
   1. rerun the canonical trusted repo change positive, negative, campaign, and offline verifier commands
   2. run `python scripts/governance/check_docs_project_hygiene.py`

## Rollback Plan
1. Rollback trigger: The bounded trust/publication wording is found to overclaim beyond the shipped proof slice.
2. Rollback steps:
   1. remove the new spec and evaluator guide
   2. remove the README support section and docs index entries
   3. restore `CURRENT_AUTHORITY.md` to the pre-publication-boundary proof wording
3. Data/state recovery notes: No durable runtime state migration is involved.

## Versioning Decision
- Version bump type: New durable contract
- Effective version/date: 2026-04-18
- Downstream impact: Public proof-backed wording must now stay scoped to `trusted_repo_config_change_v1`, must name `verdict_deterministic` as the current claim ceiling, and must explicitly state that replay and text determinism are not yet proven for that slice.
