# Operator Completion Acceptance

## Summary
- Change title: Base card/run operator verification on inspected retained acceptance.
- Owner: Orket Core.
- Date: 2026-09-12.
- Affected contracts: `docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md`,
  `docs/API_FRONTEND_CONTRACT.md`, `docs/specs/CARD_VIEWER_RUNNER_SURFACE_V1.md`,
  operator view filters and verification fields.

## Delta
- Opening behavior: source-attribution metadata alone yields a verified run;
  raw done rows enter the completed card list, while enum-valued card detail
  payloads are misclassified as open. Evidence loss does not revoke these claims.
- Required behavior: application-owned card reads share current receipt inspection
  with the execution graph. Accepted done and guard-approved cards enter completed;
  successful-looking lifecycle without acceptance requires review. Card summaries
  describe the card; the last run remains a separately named historical projection.
- Run verification requires a successful retained run outcome that exactly matches
  a fresh sufficient build inspection, including expected IDs and receipt digests.
  Missing, stale, substituted or unverifiable outcomes cannot confer verification.
  Source attribution remains separately visible and cannot replace acceptance.
- Raw lifecycle remains unchanged. Verification describes retained declared
  criteria, not all possible objective quality or current workspace contents.
- Unfiltered pagination applies offset once; the existing filtered scan bound
  remains explicit and does not imply an unbounded total.

## Migration Plan
1. Keep existing endpoints and filters; attach completion diagnostics to view
   responses. Normalize typed cards with JSON-mode serialization.
2. Historical receiptless cards and runs without retained build outcomes remain
   visible but unverified. No migration or evidence recapture occurs on read.
3. Prove list/detail/filter parity, both accepted statuses, missing/foreign/legacy
   prerequisites, stale outcome/evidence, attribution-only negatives and live TCP.

## Rollback Plan
1. Trigger: valid retained acceptance hidden or unsupported completion promoted.
2. Repair shared inspection/projection. Do not restore source-attribution-only
   verification or status-only completion filters.

## Versioning Decision
- Effective date: 2026-09-12; no commit, release or version bump in this checkpoint.
- Completed filter semantics now require acceptance; clients retain `raw_status`
  for lifecycle. Other execution families need their own admitted completion proof.
