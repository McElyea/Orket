# Contract delta: typed runtime outcomes

## Summary
- Owner: Orket Core, architectural-truth BT-4.
- Date: 2026-09-13.
- Affected contracts: epic publication/finalization/recovery, public runtime
  dispatch and compatibility wrappers, collection admission, CLI narration/exits.
- Durable contract: `docs/specs/RUNTIME_EXECUTION_RESULT_CONTRACT.md`.

## Delta
- Prior behavior: publication returned only a transcript. A real installed
  llama.cpp run retained `terminal_failure` for missing required attribution but
  `--card`, `--epic` and `--rock` returned zero; two printed completion wording.
  Approval denial also returned normally after recording failure.
- Required behavior: application-owned typed observations preserve retained run
  and final-truth records, confirmed publication, evidence references, uncertainty
  and transcript history through every dispatch layer. Callers use the typed
  outcome before claiming success or admitting dependent work.
- Reuse the existing control-plane vocabulary and publication journal. An
  unresolved or cancelled observation must not fabricate a terminal record.
- Cancellation remains an `asyncio.CancelledError` with a typed observation after
  cleanup. Admitted business failures return typed failed outcomes; errors before
  admission remain explicit errors. Unconfirmed effects remain unresolved.

## Migration Plan
1. Effective only in the unreleased architectural-truth worktree. Existing runtime
   method names remain; their transcript/list return shape intentionally changes
   to the typed outcome. Migrate repository callers to explicit history/outcome
   consumption. No list/dict compatibility emulation or hidden executor is added.
2. Existing CLI arguments and the source `main.py` wrapper remain supported through
   the declared 0.6.x compatibility window. They share one outcome projection:
   success 0, other returned execution outcomes 1, cancellation 130, usage 2.
   Interactive EOF/quit behavior remains unchanged.
3. Preserve retained histories without rewriting terminal states or inventing
   missing evidence. Revalidate publication on recovery and return the retained
   outcome instead of redispatching to reconstruct a result.
4. Verify real public runtime/CLI boundaries, interrupted recovery, collections,
   aliases, installed Windows/Linux cells, and live llama.cpp success/failure.
   The canonical plan retains exact proof and remaining limitations.
5. Collection child identities now append `-member-<1-based index>` to group
   session/build IDs. Existing histories are retained; there is no automatic
   identity migration or reinterpretation of earlier shared-identity collections.
6. Approval API responses add `runtime_result` when continuation observes an epic
   outcome. Extension action callers receive the explicit typed serialization on
   success; a non-success result raises `RuntimeOutcomeError` with that observation.
   Probe serializers and native recovery test workers consume this contract too.
7. The CLI preserves the typed cancellation observation after engine cleanup,
   including known run/evidence references, while returning 130. It must not
   discard that observation through the generic interruption handler or invent
   a cancelled durable state.

## Rollback Plan
1. If result identity, classification or publication confirmation is wrong,
   disable the affected admission/result path while repairing the owner.
2. Preserve records and unconfirmed admissions. Do not restore transcript-only
   success, zero exits for failed outcomes, or an unsupervised fallback.
3. Recovery must use retained evidence and cannot replay tool/model effects merely
   to regenerate a response shape.

## Versioning Decision
- This is a public return-contract break in the unreleased remediation worktree,
  intended for the architectural-truth compatibility cutover.
- No release/version bump, tag, commit or push is performed by this checkpoint.
- CLI failure exits are a correctness repair; method callers must explicitly
  consume the typed result and its transcript projection.
