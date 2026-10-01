# Outward store initialization and transaction lifetime

## Summary
- Change title: capture outward initializer/UOW database selection and retain native resource phases.
- Owner: Orket Core.
- Date: 2026-09-28.
- Affected contracts: `docs/specs/OUTWARD_APPROVAL_EFFECT_LIFECYCLE_V1.md`; shared owner remains `docs/specs/SHARED_IO_CANCELLATION.md`.
- Status: implemented; scoped Windows source closing passes; installed/platform acceptance pending.

## Delta
- Current behavior: initialization can leave native work behind when interrupted;
  a boolean cache can falsely mark a rebound database initialized. UOW path
  resolution, preflight and resource phases have incomplete native ownership.
  Public borrowed CRUD may initialize an unrelated mutable store path before
  operating on the caller's selected connection.
- Proposed behavior: use existing per-store locks, migration bodies and shared
  I/O owner to retain one captured-path initialization. Cache only a fully closed
  successful path. Capture all three store references/paths before UOW preflight;
  use their resolved agreement throughout initialization and child construction.
  Retain acquisition, preparation, commit and rollback/close without moving the
  yielded application body into a different task. Preserve public store delegates.
- Intentional raw embedding change: supplied connections now own their schema;
  optional-connection CRUD skips unrelated `ensure_initialized`. Empty selected
  schema refuses normally; caller transaction/connection remain borrowed. The
  repository's four raw fixture sites already initialize their selected schema.
- Failure/effect semantics: interrupted native commits may be durable. Native
  acknowledgement failures remain failures. Successful cleanup preserves a
  selected body failure; native rollback/close failures supersede it. Rollback
  failure still attempts close. Native `CancelledError` remains a failure, even
  after caller interruption; cleanup uses the additive shared `finish_owned_io`
  result policy only while a body/admission failure is already selected. With no
  selected failure, ordinary shared ownership still reports caller cancellation.
  No retry, repair or authority rule changes.
- Why now: close this bounded D2/D3 family without adding a second lifecycle loop,
  cloning stores, resetting their locks/caches, or bypassing public CRUD seams.

## Migration Plan
1. No compatibility shim/window. Concrete UOW composition supplies its captured
   path to `OutwardStoreTransaction`; no other repository constructor caller was
   found. Raw borrowed callers explicitly initialize the selected schema first.
2. First apply the reviewed additive shared finalizer entry from the finalizer
   ownership slice; it composes the existing settlement implementation. Keep
   migrations, SQL, immutable proposal rules and transaction algorithms;
   reuse the current path-capture and native ownership authorities. No data rewrite.
3. First apply only the new fixture/tests against exact unchanged product bytes.
   Retain original failures, then apply product/spec changes and run all controls
   plus existing outward admission, authorization, migration, ledger and WAL guards.
   Native controls use actual held SQLite/metadata operations, repeat cancellation,
   observe real deadline interruption, sibling SQLite progress, exact exception
   identity, retained rows, connection closure and joined worker threads.
4. Source/installed interpreter/platform acceptance remains a separately retained
   gate. Static candidate checks establish no runtime result.

## Rollback Plan
1. Trigger: broken admission, migration, refusal, transaction ownership or failure precedence.
2. Revert this bounded product/spec change together; retain observations and reopen
   the exact D2/D3 obligation. Do not mask a failure by accepting another outcome.
3. Inspect retained state before retry: migration and commit may already have
   succeeded despite interruption/acknowledgement failure. Do not delete history,
   relabel approval authority or redispatch external effects.

## Versioning Decision
- Version bump type: none for this internal remediation candidate.
- Effective version/date: current 0.6.114 source candidate, 2026-09-28; scoped
  source closing passed; installed acceptance remains separately pending.
- Downstream impact: direct borrowed SQLite embeddings must prepare their selected
  schema. Arbitrary subclass/hook compatibility, standalone CRUD/writer lifetime,
  arbitrary body workers and nested mutable request payloads remain outside scope.


## Observed source proof

Opening v2: **102 failed, 20 passed** in 6.97s, 5,569 unchanged inputs. The failures
cover native early return, incomplete migrations/cache, redirected inputs,
unrelated borrowed initialization and failure/deadline identity. One native-close
case already preserves cancellation identity but lacks the newly required body
context; it is a new causal-context requirement, not a native-identity defect.
Twenty existing behaviors pass. No held-operation expiration or fixture cleanup
failure was observed. Original opening is retained at
`.tmp/goal-20260928-outward-store-opening-v2-*`.

After the reviewed four-store correction and explicit shared-owner supplement,
all 122 controls pass within the **452**-case, 38-selector closing. All 5,570
Git-visible inputs remain unchanged. Existing public admission/process races,
authorization, approval/effect/model recovery, offline migration, ledger, WAL
and native-owner guards are included. All native-cancellation identities and the
new causal context assertion pass. Evidence:
`.tmp/goal-20260928-store-finalizer-closing-v1-*`; exact application/support
binding: `.tmp/d-outward-store-lifetime-v2-20260928/`.

Proof is live local native/files/SQLite/process and public application routes with
declared contract limits, path primary, result success. The finalizer supplement
changes only its additive result policy; the existing six shared-owner declarations
retain AST equality. Current source is tested. Standalone CRUD/event-writer,
arbitrary body workers, nested payloads, installed packages and Linux remain open.


Subsequent Windows Python 3.12 **source** closing: **271 passed** across 12
selectors in 112.36s; all 5,586 Git-visible inputs were unchanged and equal to
the 697-case Python 3.11 closing snapshot. All 259 shared case identities pass;
the additional native-owner controls retain their own scope. This includes all
122 outward store, 20 finalizer, 18 epic cleanup, 34 failure-report, 32 supporting
diagnostic and seven component-construction controls. Evidence:
`.tmp/goal-20260928-new-ownership-source-py312-v1-*` and
`.tmp/goal-20260928-composition-ownership-parity.json`. All 4,956 historical
installed bindings remain unchanged. Reusing that environment's interpreter
with current source is not fresh installed-wheel acceptance. Linux, current
installed and broader quality/capability gates remain separate.
