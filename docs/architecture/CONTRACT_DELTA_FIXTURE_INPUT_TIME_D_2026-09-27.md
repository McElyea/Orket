# Fixture admission and selected verification time

## Summary
- Owner: Orket Core. Date: 2026-09-27.
- Status: Active implementation in checkpoint 0.6.113; scoped
  current-source proof passes, installed acceptance remains pending.
- Trigger: four retained input/native-ownership opening failures, plus implicit
  verification clocks and the touched unowned security-publication await.
- Contracts: runtime verification ownership, verification process lifetime,
  sandbox HTTP verification, epic runtime time and log-write settlement.

## Delta
- Fixture invocation detaches supported scenario graphs and captures root,
  environment and selected provider methods before waiting. Exact standard schema
  models and built-in graphs replace implicit custom-value copy/serialization hooks.
- The existing built-in copier is extracted once to a generic core contract with
  caller-specific stable error codes. Existing log-event API/behavior stays intact.
- The existing native I/O owner retains metadata through repeated cancellation and
  timeout. OSError/ValueError during an interrupted drain escapes; ordinary invalid
  policy or metadata failure still maps to the existing failed result without a child.
- Both services require explicit aware `utc_now`. Orchestration binds its selected
  turn clock, workspace and environment before card lookup and forwards the clock.
  Each stage samples once and normalizes offsets to UTC without a host-clock fallback.
- HTTP transport factory and timeout selection also capture before owned observation
  scheduling. The same HTTP owner receives them explicitly; replacement of service
  attributes does not change this invocation, while factory internal state is borrowed.
- Required security publication uses the existing owned native boundary. Successful
  publication followed by interruption propagates cancellation; a native publication
  failure takes precedence over interruption. Uninterrupted successful publication
  still raises the original security refusal. No required event becomes a supporting
  diagnostic note. Captured-root lifetime publications retain their existing owner
  loop and outcome precedence; no writer/lifecycle redesign is introduced.
- Scenario publication remains replacement after settled execution, without a
  concurrent-edit merge, transaction or stronger completion authority. Native
  append/child effects may remain after failure or interruption.

## Migration Plan
1. Pass `utc_now` to both direct constructors. Fixture `runtime_inputs` retains
   identity only; sandbox's timestamp-only option retires without a shim.
2. Convert custom payload types explicitly to supported built-in values. Stable
   fixture refusal is `E_FIXTURE_VERIFICATION_INPUT_UNSUPPORTED`; invalid time
   refuses with `E_VERIFICATION_TIME_REQUIRES_AWARE_DATETIME`.
3. Preserve real child/HTTP/SQLite and event-capture regressions. The retained
   input/metadata opening is four failures/one healthy pass; the security opening
   is four interruption-ownership failures/two uninterrupted passes. Closing has
   46 controls (38 input/time controls, six security-publication controls and two
   HTTP-port controls) plus 165 existing guards passing. Declared container ports
   prove input policy only, not Docker.
4. Live Docker, installed/native-platform and broader D acceptance remain separate
   obligations. Fixture tombstone retirement remains on its existing ticket.

## Rollback Plan
Revert capture extraction, service and caller changes together if ownership,
precedence or event parity fails. Preserve openings and disclose restored input
borrowing/unowned awaits. Do not introduce partial compatibility fallback.

## Versioning Decision
The implementation is included in patch checkpoint 0.6.113. Its breaking
embedding migration and incomplete wider acceptance are recorded in CHANGELOG.md
and the architectural-truth plan. Publication does not close those obligations.

## Scoped proof and limits

Windows Python 3.11 copied-source closing passed 211 distinct cases: 152 integration
and 59 contract. An initial affected-clock rerun is already one of those 211 cases;
212 body invocations do not mean 212 distinct controls. Exact cases, imports,
native owner receipts and file/SQLite readback are bound in the local
`.tmp/d-fixture-inputs-proof-v4/final-review.json` receipt. All owners were reaped
without timeout, observed residual or emergency cleanup. Readback includes three
stopped native descendant identities, six required append records, real HTTP and
the persisted selected-clock result after engine close. Injected-hold independent
SQLite observations retained the 0.5-second response bound. Empty query-only
database files were reopened read-only without claiming persisted rows.

The proof used the preserved 0.6.111 source copy plus these candidate bytes and
separately recorded active editable 0.6.112 metadata. No published 0.6.112-changed
path appeared in the selected import origins; direct baseline bindings matched
before application. This is copied-source evidence, not current-worktree or
installed acceptance. A separate current-worktree invocation now passes the exact
211 cases with 807 bound source origins, 33 reopened SQLite artifacts, three stopped
native identities and six settled required publications. Its owner is reaped
without timeout or observed residue. Readback:
`.tmp/d-fixture-inputs-current-v1/current-source-review.json`, SHA-256
`9b0592a56b86e46b67bf8684ae86d95882edd8ba0fa6806856fc582dc5086f1c`.
Installed/Linux, actual Docker and provider proof remain separate. Earlier runtime openings and failed
harness/fixture candidates are retained without reclassifying setup mistakes as
runtime findings. This slice does not close the full D inventory.
