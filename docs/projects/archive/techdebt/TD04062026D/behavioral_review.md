# Orket — Behavioral Review

**Date:** 2026-04-06
**Reviewer:** Claude (Sonnet 4.6)
**Scope:** Runtime semantics, control flow, async behavior, state machine correctness, fallback paths, and test fidelity
**Note:** This review focuses on what the system *actually does* at runtime versus what the contracts, docs, and method names claim it does. An earlier behavioral review was conducted 2026-03-17 and archived. This review is a fresh assessment of the current state.

---

## BH-1. The ODR reactor presents a pure-functional interface but secretly shares mutable state

**Affected:** `orket/kernel/v1/odr/core.py` → `run_round`

The ODR (Ordered Deterministic Reactor) is the correctness kernel of the entire system. Its central claim is deterministic, replayable execution. `run_round` takes a `ReactorState` and returns a `ReactorState`. Callers reasonably assume they can snapshot state before calling, compare states after calling, or call multiple times with the same input to verify determinism. None of this is safe because `ReactorState` is a plain mutable dataclass and `run_round` mutates it in-place before returning the same reference.

The behavioral consequence: any caller that saves a reference to the state before `run_round` and checks it afterward to verify "no change" will see the mutation. Any test that calls `run_round` twice with ostensibly the same initial state will actually be running on a state that was already mutated by the first call. The ODR's own determinism tests may be passing not because the system is deterministic, but because the mutation is consistent — an important distinction.

---

## BH-2. The `stage_triplet` behavior cannot be predicted from reading the class

**Affected:** `orket/kernel/v1/state/lsi.py`

The LSI (Local Sovereign Index) is the artifact and triplet storage layer for the kernel. When a developer reads the `LocalSovereignIndex` class to understand how `stage_triplet` works, they read a method body that unconditionally raises `RuntimeError`. The actual behavior — the grouped update implementation — lives in a module-level function that replaces the class method at import time.

The behavioral lie: the class body says the method fails with an internal contract error. The runtime says the method works via a grouped update. These are completely different behaviors. This means:

- Any attempt to mock or stub `stage_triplet` by subclassing will get the crash behavior unless the mock also replicates the monkey-patch.
- Debuggers and traceback tools will show the wrong method body for the active call.
- `help(LocalSovereignIndex.stage_triplet)` will show the wrong docstring and signature until after import completes.

---

## BH-3. Canonicalization output depends on which import path is taken, not on intent

**Affected:** `orket/kernel/v1/canon.py`, `orket/kernel/v1/canonical.py`

Two modules both claim to produce a canonical, stable representation of a JSON-like object for determinism and integrity checking. They produce fundamentally different outputs for the same input.

The behavioral consequence: the system has two incompatible notions of "content identity" running simultaneously. The ODR determinism gate pins hashes produced by `canon.py`. The LSI stores digests computed by `canonical.py`. A developer who queries "is this artifact the same as what the determinism gate expects?" cannot get a meaningful answer because the hash spaces are incomparable.

The deeper behavioral problem is that neither system documents which keys are "non-semantic" (should be stripped for comparison purposes) at the policy level. This means the stripping logic in `canon.py` (`timestamp`, `path`, `run_id`, etc.) is embedded in the serializer rather than in a policy declaration. When a new non-semantic key is added anywhere in the system, someone has to know to update `canon.py` to strip it — there is no enforcement mechanism.

---

## BH-4. Spool fallback for sandbox lifecycle events creates a false sense of durability

**Affected:** `orket/application/services/sandbox_lifecycle_event_service.py`

When the primary repository fails, `emit()` spools the event to a local file and returns `"fallback"`. The return value communicates that something happened — the event is "safe." But:

1. The spool file is on local disk. If the machine running the service crashes, the spool is lost.
2. `replay_spool` silently re-queues records that fail replay with no retry cap. A record that the repository permanently rejects (schema mismatch, invalid data) will be re-queued indefinitely.
3. The caller receives `"fallback"` and has no way to know if spool drain has ever been attempted, how many records are in the spool, or whether any have been permanently rejected.

The behavioral contract implied by the return value `"fallback"` is "your event is safe, we'll retry it." The actual behavior is "your event is on local disk and may be lost or permanently stuck."

---

## BH-5. The ControlPlane convergence lane is paused with known incomplete behaviors

**Affected:** `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_IMPLEMENTATION_PLAN.md`

The control plane convergence plan is explicitly paused. The plan documents eight known gaps that are not yet closed:

1. Workload identity remains conflicting.
2. Attempt history is not yet universally first-class.
3. Reservation and lease truth are not yet universal across admission and scheduling.
4. Effect truth is still often reconstructed outside the normative effect journal.
5. Checkpoint publication and supervisor-owned checkpoint acceptance are not execution-default.
6. Operator-action authority remains fragmented outside selected paths.
7. Namespace and safe-tooling gates are not yet universal across broader workloads.
8. Closure truth risks remaining split between new control-plane records and older summary surfaces.

The behavioral consequence: the runtime behaves differently depending on which code path is active. Some paths publish full control-plane truth. Others reconstruct effect truth from scattered artifacts. For any consumer of the control plane API, the system's stated guarantees about workload lifecycle, reservation, and effect authority do not uniformly hold.

This is documented and acknowledged, but it is the most significant behavioral gap in the current system.

---

## BH-6. `transition_state` can return a record that was modified by a concurrent writer after the mutation committed

**Affected:** `orket/application/services/sandbox_lifecycle_mutation_service.py`

The mutation service fetches the record, validates and applies the mutation, and then fetches it again to return the result. Between the mutation commit and the second fetch, another concurrent writer may have applied another transition. The returned record will show the other writer's state, not the state that was just written. Callers that use the returned record to confirm "my transition succeeded" may be reading a lie.

The correct behavior is to return the record that was atomically written, not a post-write re-fetch. The return value from `apply_record_mutation` should carry this.

---

## BH-7. `replay_spool` is not concurrency-safe

**Affected:** `orket/application/services/sandbox_lifecycle_event_service.py`

`replay_spool` reads the entire spool file, processes all records, then rewrites the file. There is no file lock. If two callers invoke `replay_spool` concurrently (e.g., on startup, or via a periodic background task), they will both read the same records, attempt to replay all of them (duplicating writes to the repository if the repository is not idempotent), and then both write their own "remaining" list, with the second write potentially overwriting the first's output and losing the records that the first call correctly retained.

---

## BH-8. `run_companion_provider_runtime_matrix` treats every HTTP failure identically

**Affected:** `scripts/companion/run_companion_provider_runtime_matrix.py`

The matrix runner makes HTTP requests to the companion API for each provider/model/rig combination. All HTTP failures (connection refused, 401, 500, timeout) are collapsed into a single failure case with no differentiation. A 401 (wrong API key — operator error) looks the same in the output as a 500 (server bug) or a timeout (performance regression). This means matrix report failures are ambiguous and require manual investigation to diagnose.

---

## BH-9. Tool approval denial and risk acceptance use the same `action_id` format, making them indistinguishable in action logs

**Affected:** `orket/application/services/tool_approval_control_plane_operator_service.py`

Both the denial path and the risk-acceptance path produce `action_id` values with the format `approval-operator-action:{approval_id}:{decision_token}:{timestamp}`. Since `decision_token` is derived from the resolution record's `decision` field, which may be absent and defaults to `"approve"`, a denial that lacks an explicit `decision` field and an approval that has one produce structurally similar action IDs. Idempotency checks based on `action_id` may deduplicate across denial and approval operations.

---

## BH-10. The CI dry-run smoke for the quant sweep never validates actual execution behavior

**Affected:** `.gitea/workflows/quant-sweep-smoke.yml`

The smoke CI job runs the quant sweep with `--dry-run`. This means the CI gate for the quant sweep infrastructure validates only that the argument parsing and matrix expansion logic work — not that the sweep can actually connect to a model, run a session, or produce meaningful output. A breakage in the execution path (e.g., a broken import in the runner, an API contract change) will not be caught by this gate.

---

## Summary

| ID | Area | Behavioral Gap |
|---|---|---|
| BH-1 | ODR / kernel | Functional API secretly mutates state |
| BH-2 | LSI / kernel | Class method body is a crash stub; real impl is a post-definition monkey-patch |
| BH-3 | Canonicalization | Two active systems produce incomparable hashes for identical inputs |
| BH-4 | Lifecycle event spool | Fallback implies durability; actual behavior does not provide it |
| BH-5 | ControlPlane | Eight documented incomplete behaviors remain in the paused convergence lane |
| BH-6 | Lifecycle mutation | Return value may reflect concurrent writer's state, not the committed mutation |
| BH-7 | Spool replay | Not concurrency-safe; duplicate writes and lost records under concurrent callers |
| BH-8 | Companion matrix | All HTTP failure classes treated identically |
| BH-9 | Tool approval | Denial and approval produce similar action IDs; idempotency may misfire |
| BH-10 | Quant sweep CI | Dry-run gate misses actual execution breakage |
