# Orket — Behavioral Review

> Focuses on runtime behavior, policy enforcement, agent contracts, and observable system properties. References code issues by number where relevant.

---

## B1. ODR loop treats `MAX_ROUNDS` as a valid success path

`run_live_refinement` runs up to `attempt_budget` rounds. The calling code in `cards_odr_stage.py`:

```python
_ACCEPTABLE_MAX_ROUNDS_STOP_REASON = "MAX_ROUNDS"

def _odr_prebuild_accepted(*, stop_reason: str, odr_valid: bool, pending_decisions: int) -> bool:
    ...
    if normalized_stop_reason in _SUCCESS_STOP_REASONS:
        return True
    # ...allow non-default prebuild path when valid and decision-complete at max rounds
```

A run where the architect and auditor oscillate without converging — never reaching `STABLE_DIFF_FLOOR` or `LOOP_DETECTED` — will exhaust the round budget and exit with `MAX_ROUNDS`. Depending on `odr_valid` and `pending_decisions`, this can be accepted as a successful prebuild. An infinite oscillation masked by the round cap passes downstream as a completed work item. The ODR loop needs an explicit convergence-failure outcome that blocks prebuild acceptance, separate from "we ran out of budget."

---

## B2. AGENTS.md mandates direct `main` commits with no PR gate

`AGENTS.md` section "Repo Discipline" states: "Work directly on `main` unless the user explicitly requests a branch workflow." Combined with the Gitea CI pipeline, this means every commit — including agent-generated commits — lands on the protected branch without a PR review cycle. The `core-release-policy.yml` workflow validates commits after the fact, but it cannot reject them retroactively. A failing governance check on a direct push produces a CI failure with no rollback mechanism. The behavioral contract should either require PRs by default (with direct-main as the exception) or include an automated rollback trigger on governance failure.

---

## B3. Auto-merge fires on `approved` state without validating PR is open

`PRReviewHandler.handle_pr_review` calls `self.auto_merge(repo, pr_number)` whenever `review_state == "approved"`. There is no pre-check on whether the PR is still open, not already merged, or not in a draft state. Gitea can deliver review events for already-closed PRs (e.g., via webhook replay or event redelivery). The auto-merge call on a closed PR will return an error, but the handler will surface this as a merge failure rather than "PR was already closed." This can trigger spurious error notifications and confuse the PR lifecycle state machine.

---

## B4. PR escalation cycle counter is not durable (B1 compound: Code Issue #25)

The `WebhookDatabase` backing the `handler.db.increment_pr_cycle()` call is initialized without a persistent path. A process restart resets all cycle counts to zero. A PR author who reaches two review cycles can escape the architect escalation threshold indefinitely by any event that restarts the webhook handler (deploy, crash, config change). The escalation policy is behavioral theater unless the counter state survives restarts.

---

## B5. `NullControlPlaneAuthorityService` silently degrades the control plane

When `Agent` is constructed without a `journal`, it gets `NullControlPlaneAuthorityService`, which returns `None` for all journal calls. Nothing in the runtime logs that journaling has been disabled. An operator who expects effect journal entries to be produced will get a silently empty journal. The null seam is necessary for lightweight agent use, but its activation must be logged at `warn` level to make the degradation observable.

---

## B6. Tool gate stored on Agent but enforcement path is opaque

`Agent.__init__` stores `self.tool_gate = tool_gate`. The tool gate is described in the SDK as "mechanical enforcement" of which tools may be called. But there is no visible call to `tool_gate.check()` or `tool_gate.enforce()` in the agent turn execution path visible in the dump. If the gate is only checked in certain execution branches (e.g., the OpenClaw adapter but not the direct tool dispatch path), agents operating through the direct path bypass all tool governance. This is a silent security boundary failure — the gate exists but doesn't gate.

---

## B7. Policy resolver ignores unrecognized top-level keys — misconfiguration is invisible

A repo's `.orket/review_policy.json` with a typo (`"lane"` vs `"lanes"`, `"deterministc"` vs `"deterministic"`) gets deep-merged silently. The resolved policy looks correct internally but the intended override has no effect. The review runs with defaults, and the user sees passes or changes-requested that don't reflect their configuration. This is a behavioral bug masquerading as a content issue: the system behaves correctly with respect to what it read, but incorrectly with respect to what the user intended.

---

## B8. Streaming drop behavior produces invisible data loss for producers

When `StreamBus.publish()` drops a best-effort event, it returns `None`. The agent or service emitting the event has no feedback signal. In the token-streaming path where intermediate content events are best-effort, silent drops mean the consumer sees a truncated stream without any truncation marker. The consumer may interpret this as a complete response. The correct behavior is to emit a `STREAM_TRUNCATED` advisory event when the budget is exhausted, so consumers can signal incomplete rendering.

---

## B9. Review policy `forbidden_patterns` includes a TODO/FIXME check that will block legitimate comments

```json
"forbidden_patterns": ["(?i)\\b(todo|fixme)\\b", "(?i)password\\s*="]
```

The `TODO|FIXME` pattern in `forbidden_patterns` will flag any added line containing these words, including unit test comments (`# TODO: add more cases`), documentation (`This addresses TODO #42`), and any string literal containing these words. This is checked by the deterministic lane and produces `FORBIDDEN_PATTERN` findings with severity `high`. A developer adding a test stub with a `# TODO` comment will get a `changes_requested` decision on their PR. The pattern is too broad to be a `high`-severity check by default and should either be severity `info` or require a more precise pattern.

---

## B10. `cards_odr_stage._resolve_odr_max_rounds` silently caps at 1 on parse failure

```python
parsed = _coerce_int(raw)
if parsed is None:
    return int(default)
return max(1, parsed)
```

If an operator sets `odr_max_rounds: 0` intending to disable the ODR pass, `max(1, 0)` silently sets it to 1 and runs one round anyway. Zero should be a valid value meaning "skip ODR." The floor of 1 is a behavioral override that contradicts operator intent and produces unexpected behavior without any log or warning.

---

## B11. `build_team_agents` creates broken agents for misconfigured roles without failing

When a seat's role name doesn't appear in `role_configs`, the factory logs a `seat_role_config_missing` warning and continues with an empty tool set. When `scoped_tool_map` is empty, `strict_config=False`. The agent is created, registered, and dispatched to — but it has no tools and will likely produce empty or malformed outputs. From the orchestration layer's perspective, the agent ran. From the operator's perspective, nothing happened. A misconfigured role should fail at team construction, not at runtime.

---

## B12. `ControlPlaneAuthorityService.publish_checkpoint` is a no-op — checkpoints are never recorded

`publish_checkpoint` is called at strategic points in the control plane protocol to mark safe-to-resume points. The current implementation returns the input unchanged without persisting it anywhere. If the process crashes after a checkpoint is "published," recovery cannot find it and must restart from scratch or mark the run as irrecoverable. The checkpoint mechanism is currently providing false safety: callers believe they have established a recovery point, but none exists.

---

## B13. Dual-write ledger's file-based intent log creates a second failure window (Compound: Code Issue #17)

The `AsyncDualModeLedgerRepository` writes an intent file before executing dual-write operations and clears it afterward. If the process crashes mid-operation, recovery replays from the intent file. However, SQLite's WAL already provides atomicity for each individual write. The intent replay can issue an operation that was already committed (if the crash happened after commit but before intent-file clear), producing a duplicate record. Unless `start_run` and `finalize_run` are idempotent by run ID (i.e., use `INSERT OR IGNORE` or equivalent), this is a correctness bug in the recovery path.

---

## B14. `GiteaStateAdapter` token is `SecretToken(str)` subclass — but still logs on comparison

```python
class SecretToken(str):
    def __repr__(self) -> str:
        return "SecretToken(***)"
```

`__repr__` is masked, but `__str__` is not overridden — it returns the raw token value. Any `log_event` call, f-string, or `str()` conversion of the token will leak it. The protection is incomplete. `__str__` and `__format__` must also be overridden to return the masked representation.

---

## B15. `run_service._git_paths` uses `subprocess.run` with `check=True` — no timeout

The git subprocess call has no timeout parameter. In a CI environment with a large repository or a network-mounted git store, `git diff --name-only` can hang indefinitely. The review runner will block on this call forever. The `subprocess.run` call needs a `timeout=` argument, and the `CalledProcessError` and `TimeoutExpired` should be caught and converted to structured `ReviewError` instances.

---

## B16. `EnvironmentConfig` emits a `DeprecationWarning` on unknown keys — wrong warning type for config schema enforcement

```python
warnings.warn(
    "EnvironmentConfig ignored unknown key(s): ...",
    DeprecationWarning,
    stacklevel=2,
)
```

`DeprecationWarning` is filtered by default in Python unless explicitly enabled. In production, operators adding unknown config keys will see no warning at all. The warning should be `UserWarning` (visible by default) or, better, should raise `ValidationError` in strict mode. Using `DeprecationWarning` for a live configuration schema mismatch is semantically wrong — the key isn't deprecated, it's unrecognized.

---

## B17. `streaming/bus.py` — subscriber queues are unbounded

```python
queue: asyncio.Queue[StreamEvent] = asyncio.Queue()
```

The subscriber queue has no `maxsize`. A slow consumer that can't drain events fast enough will accumulate an unbounded backlog. Combined with the producer-side drop logic (which drops events before queuing), a slow consumer can still cause unbounded memory growth if events are not dropped before being put into subscriber queues. The `Queue` should have a bounded `maxsize` matching the per-turn event budget, with overflow policy documented.

---

## B18. PR review auto-reject path lacks idempotency protection

`_auto_reject` is called from the review decision path but there's no guard against being called twice for the same PR (e.g., two concurrent webhook deliveries for the same review event). Two simultaneous calls would attempt to reject the same PR twice, potentially triggering two rejection comments and two status updates. Webhook event delivery is not guaranteed exactly-once; the handler needs an idempotency check against the event ID or PR state.

---

*Total behavioral issues: 18*
