# Memory state inputs, publication and lifetime

## Summary
- Change title: Captured memory inputs and atomic, owned SQLite publication
- Owner: Orket Core, architectural-truth D
- Date: 2026-09-21
- Affected contracts: project/scoped memory services, profile policy, SDK and
  extension memory admission, trust classification and rendering
- Status: implemented boundary; scoped acceptance requires the canonical plan's proof

## Delta
- Previously, nested write metadata could change during initialization or session
  admission. Project memory could follow a later cwd. SQL supplied write times;
  policy classification sampled time independently for each row. Profile policy,
  update and readback were separate transactions. Two competing first facts could
  both succeed; concurrent project duplicates could fail with a unique violation.
- Application memory services capture nested inputs and construction-time absolute
  lexical database paths. Native directory work moves to an owned worker. Path
  capture is not a resolved-handle capability or hostile-replacement containment.
  Reconstruct a service to select another database; arbitrary private runtime
  reconfiguration is outside this contract.
- Application selects an injectable `RuntimeInputService`. Mutation time is
  captured before the first await and supplied explicitly to SQL, retaining UTC
  second-precision `YYYY-MM-DD HH:MM:SS` text. Existing row timestamps and schemas
  are not rewritten. New schemas require explicit timestamp values; historical
  SQL defaults are unused by the updated write paths.
- Declared side-effecting repositories own native schema, query and write effects;
  application retains policy authority. Profile existing-state observation,
  policy evaluation, mutation and returned readback share one immediate writer
  transaction. A successful returned record describes that invocation's committed
  write, even if a later invocation replaces it.
- A shared pure logical-key normalizer applies the same confirmation/contradiction
  semantics to ordinary and `ext:<id>:user_fact.*` keys. Storage keeps the full
  namespaced identity. Stale observations cannot regress metadata even when the
  content is unchanged. Missing/invalid observation metadata retains existing
  policy semantics; this change does not invent temporal proof.
- Policy rejection keeps its existing exception type, code and message; Python
  may attach traceback state during context-manager cleanup. A frozen exception
  must not mask the policy rejection with a traceback-assignment failure.
- Project content-hash deduplication and FTS publication share a writer transaction.
  Duplicate content remains one record. Existing ranking, recency tie-breaks,
  query shapes, scope isolation and allowed-key policy remain authoritative.
- Admitted database work, rollback/commit and connection closure remain owned
  through repeated cancellation. Cancellation can follow a committed write;
  callers must inspect durable state rather than infer no effect or replay blindly.
  Native failures remain failures. Shared WAL admission, 5,000ms SQLite busy
  policy and retry restrictions remain unchanged; caller statements are not retried.
- Trust classification and rendering require explicit timezone-aware
  `observed_at`. Application samples once at each search/render boundary. Pure
  policy consumes that value for every row; no hidden wall clock fallback remains.
  Store mutation time and metadata source/observation timestamps retain separate
  meanings. Clock movement does not authorize stale metadata replacement.
- SDK writes retain accepted pre-bridge capture. Extension writes copy nested
  metadata before session admission waits. Controls retain their existing
  per-invocation evaluation; this is not a constructor-time toggle snapshot.

## Migration Plan
1. Existing public memory scopes, controls and returned values stay in their
   current application modules. Repository-private helpers are not compatibility
   authority. No new forwarding shim or duplicate policy implementation is added.
2. Direct trust classifiers/renderers supply `observed_at`; application consumers
   use the runtime input service. Async stores accept injected runtime inputs for
   repeatable observations. Reconstruct services when database selection changes.
3. Namespaced fact corrections require the same explicit `user_correction` as
   unnamespaced facts. Older metadata is refused even for unchanged content.
4. Required proof: real held SQLite writers and independent rows, nested input
   capture, profile conflict/stale-update serialization, own-write readback,
   project deduplication/FTS consistency, explicit time and legacy database parity,
   cwd rotation, held native initialization and transaction lifetime under
   cancellation/repeated cancellation/timeout, and independent responsiveness
   below the predeclared 0.5-second bound. Run affected source/installed Windows,
   SDK/application flows and opted-in real SQLite memory acceptance. Record Linux
   availability separately; no provider inference is implied by storage proof.

## Rollback Plan
1. Retain any failure and independently inspect the exact database before retrying.
   Trigger rollback if policy rejection, scope identity, returned-state truth,
   transaction teardown or accepted query semantics regress.
2. Revert services, repositories, policy callers and authority together. Do not
   rewrite historical rows or pretend an interrupted committed write did not occur.
3. Schema initialization remains idempotent; partial native failures may leave
   an initialized directory/database requiring inspection. No distributed
   exactly-once or hostile-code containment guarantee is added.

## Versioning Decision
- Version bump type: patch remediation checkpoint with explicit API/input changes.
- Effective version/date: 0.6.74 / 2026-09-21, subject to required proof.
- Downstream impact: explicit classifier/render clocks, bound database selection,
  corrected namespaced/stale profile refusal and interruption semantics above.
- Remaining limits: shared synchronous capability bridge lifecycle/blocking,
  unrelated memory systems, arbitrary custom callbacks, complete adapter
  enforcement, Linux clock acceptance, remaining D/E/CAP and lane acceptance.
