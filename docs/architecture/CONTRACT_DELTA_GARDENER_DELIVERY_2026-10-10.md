# Gardener delivery and failure contract delta

Date: 2026-10-10
Scope: GitHub issues #7, #8, #9 and the timeout follow-up on #6.

## Previous behavior

Gardener inherited a 65536-byte aggregate child-output budget. SDK model requests
counted toward that budget, so larger inputs disconnected before inference.
Independent per-message and per-materialized-input limits were not explained.
Transport failures interrupted report runs without final truth; the wrapper lost
their run identity. A title-only summary satisfied the documented delivery rule.
Generic extension HTTP timeouts escaped as unstructured internal server errors.

## New behavior and authority

- Gardener budgets 1 MiB of child output and the source report manifest permits
  that ceiling. The SDK frame cap stays unchanged. The example transports the
  complete JSON input across bounded consecutive messages; it never summarizes
  or drops evidence. Oversized individual materialized inputs refuse explicitly.
- Only host-admitted public report tasks translate settled timeout/connection
  failures into failed model receipts, with unknown usage charged at the reserved
  caps. The existing child acceptance, continuation policy and terminal publisher
  own closure. Gardener reserves five seconds for that closure and returns the
  run identity and inspect command on admitted failures. Other uncertainty keeps
  the existing recovery path. Remote inference termination is not asserted.
- `structured_report.v1` accepts optional per-section length/prefix requirements.
  Gardener requires findings and a `GARDENER_SUMMARY:` summary. Completion and
  no-residual-uncertainty classifications cover delivery only, not factual truth.
- The application translates generic generation timeout/unavailability to private
  HTTP 504/503 error envelopes. Interfaces import application errors, not core.
- Inspection projects retained uncertain-call reasons. Child failure diagnostics
  expose extracted SDK protocol codes without publishing arbitrary stderr.

Sources of truth: `GARDENER_REPORT_HARNESS.md`,
`GOVERNED_AGENT_TASK_SUBMISSION.md`, `MODEL_GENERATION_OPTIONS.md` and the current
authority manifest. Existing submissions without optional constraints retain
their original semantics. Refresh the trusted source report extension/catalog
with the updated manifest before using the updated Gardener wrapper.

## Verification and limits

Retained regression controls exercise real Git, CLI, child processes, SQLite,
HTTP and inspection/replay. Controlled responses prove transport and acceptance
behavior, not model intelligence. Actual-provider and candidate evidence, command
results, architecture checks and exact file manifest are in
`docs/releases/0.8.4/PROOF_REPORT.md`. No full-suite or hosted-CI claim is implied.
