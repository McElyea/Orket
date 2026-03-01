> **LOCKED: v0 semantics frozen. Changes to terminal reason vocabulary, legality equality rule, step_index semantics, or toy suite expectations require a v1 label and fixture updates.**

---

# Orket RuleSim v0 — Consolidated Specification
*Status: Lock candidate. All decisions herein are normative unless marked [advisory].*

---

## 0. Goal

Provide a deterministic, replayable simulation substrate for formal rule systems, exercisable in two modes:

**Validate mode:** measure balance, action usage, and outcomes under fixed strategies.

**Audit mode:** actively search for exploits, loops, and deadlocks via adversarial mutation and probing.

v0 delivers the shared base: kernel, runner, metrics, anomaly detectors, and artifacts. Higher-level designer product concerns are explicitly out of scope.

---

## 1. Scope

**In scope (v0)**

- A canonical RuleSystem interface (rules, state, actions).
- A deterministic simulation runner for N episodes with M agents.
- A strategy interface for agents (policy).
- Metrics collection (win-rate, action usage, duration, terminal reasons).
- Anomaly detectors (cycle/infinite loop, deadlock, dominance hints, illegal action attempts).
- Artifact bundle output for every run (config, seed, summaries, replays).
- A minimal mutation/probing seam so audit mode can plug in later without refactoring.

**Out of scope (v0)**

- Natural language rule parsing.
- UI / web console.
- Meta-solving and player-psychology modeling.
- Sophisticated equilibrium finding (Nash, CFR, MCTS) beyond simple strategies.
- Distributed compute / cluster scheduling (local-first assumed).
- Simultaneous move models, initiative-based scheduling, or interrupt windows.
- Information asymmetry / partial observability policy language.

---

## 2. Terminology

| Term | Definition |
|------|-----------|
| Episode | One complete simulated game/session from initial state to terminal. |
| Tick/Step | One atomic state transition driven by an action. |
| State | Serialized representation of the world at a point in time. |
| Action | Agent choice, validated by rules before application. |
| action_key | Stable canonical string identifying action class (e.g. `"play_card"`, `"pass"`). Owned by the RuleSystem. Distinct from full serialized action payload. |
| RuleSystem | Pure(ish) transition function plus legality constraints. |
| Strategy | Deterministic function selecting actions given observation. |
| Probe | A structured variation of an episode (mutated seed, policy params, or rule variant). |
| Run | Batch execution producing a single artifact bundle. |

---

## 3. Primary User Story (v0)

> "Given a formalized RuleSystem and scenario pack config, run 10,000 deterministic episodes with strategy A/B, compute balance and anomaly stats, and produce replay artifacts for the top suspicious cases."

---

## 4. Locked Decisions

The following decisions are normative for v0. They are enforced by the toy RuleSystem test fixtures (Section 12). Revisiting any of them is a v1 concern.

### 4.1 Turn Model

The runner owns scheduling. Turn order is a fixed sequence defined in the scenario config (`turn_order: [agent_id, ...]`). The RuleSystem may emit a `skip_agent` event in a TransitionResult to signal that the named agent's next scheduled occurrence should be skipped, but it cannot reorder agents. Simultaneous move models and interrupt windows are v1.

### 4.2 Action Identity

Every Action must carry a stable `action_key: str`. This is a short canonical string used for histograms, dominance detection, and anomaly records. The full serialized payload is separate. The runner uses `action_key` only; the RuleSystem owns the mapping between actions and their keys.

### 4.3 State Digest

`hash_state` must produce a deterministic SHA-256 digest (truncated to 16 hex characters is acceptable for performance) of the canonical JSON serialization of the full state dict. Canonical JSON is defined as: sorted keys, compact separators (comma and colon, no spaces), no trailing whitespace. Floats in state dicts are permitted. The runner normalizes them to 6 significant figures before hashing. If a RuleSystem emits non-JSON-serializable values, the runner raises a hard configuration error (see Section 4.5).

### 4.4 Terminal Reason Vocabulary (v0)

The following are the only valid `reason` strings for TerminalResult in v0:

| Reason | Trigger |
|--------|---------|
| `win` | RuleSystem declares a winner via `is_terminal`. |
| `draw` | RuleSystem declares no winner via `is_terminal`. |
| `cycle_detected` | Runner cycle detector fires (takes priority over timeout). |
| `deadlock` | Current scheduled agent has no legal actions. |
| `timeout` | max_steps reached without any other terminal condition. |
| `invalid_action` | Illegal action policy set to `terminal_invalid_action` and illegal action observed. |

### 4.5 State Serialization Validation

On first encounter of a non-JSON-serializable value in a state dict, the runner raises a configuration error and aborts the run. The error must include the full key path of the offending value (e.g. `state["hand"][0]` is non-serializable type `Card`). This is a RuleSystem bug, not a runner concern.

### 4.6 Illegal Action Policy

The runner validates every action against `legal_actions` before calling `apply_action`. The policy is mode-scoped and set via config:

| Policy | Behavior |
|--------|---------|
| `substitute_first` | Record `illegal_action_attempt` anomaly; substitute `legal_actions[0]` deterministically; continue episode. Default for v0 validate mode. |
| `terminal_invalid_action` | Record anomaly; terminate episode with reason `invalid_action`. Available for audit mode. |

The substitution fallback is always `legal_actions[0]` — deterministic, not random.

### 4.7 Cycle Detector Termination Priority

Cycle detection fires after each state transition, not before. The repeat condition is: `hash_state(current_state)` matches any previously seen state digest in the current episode (full history, not a sliding window). When a cycle is detected, the episode terminates immediately with reason `cycle_detected`. This takes priority over timeout.

### 4.8 Turn Snapshot Invariant

On each agent turn, the runner derives `observe(state, agent_id)` and `legal_actions(state, agent_id)` from the same pre-action state snapshot. Strategies receive the resulting observation and legal_actions as a matched pair for that snapshot. The runner calls both before strategy selection; call ordering is fixed but irrelevant because both must be pure with respect to the snapshot.

Observation is a projection: `observe()` may return a subset or transformed view of state. It must be deterministic and must not mutate state.

### 4.9 Action Legality Equality

A proposed action is legal if and only if `canonical_json(serialize_action(action))` exactly matches `canonical_json(serialize_action(a))` for at least one `a` in `legal_actions`. The runner uses canonical JSON comparison — not Python object identity, not `action_key` alone. This is the authoritative legality check before every `apply_action` call.

### 4.10 skip_agent Semantics

`skip_agent` in a TransitionResult applies to the next scheduled occurrence of the named agent only. It does not persist beyond skipping a single turn. Multiple `skip_agent` signals targeting the same agent before their next occurrence collapse to one skip (idempotent). If the target is the current agent, the skip applies to their next occurrence, not retroactively to the current turn.

### 4.11 Step Index Semantics

`step_index` refers to the count of attempted agent turns — each scheduled agent opportunity in `turn_order`. `max_steps` bounds `step_index`, not round count. A `round_index` may be derived as `step_index // len(turn_order)` but is not a first-class runner counter.

A skipped turn counts as an attempted turn and increments `step_index`.

A terminating deadlock or invalid-action event occurs at the current `step_index`; `step_index` is not incremented after termination.

`cycle_length` is defined as `current_step_index - first_seen_step_index`, where both indices use the same `step_index` counter. It represents the number of transitions between the first occurrence of the state and the transition that returns to it.

The digest map tracks states observed after each transition, with the initial state seeded at `step_index=0`. This ensures `cycle_entry_step=0` is reachable when the initial state recurs.

---

## 5. Contracts

### 5.1 RuleSystem Contract

A RuleSystem must provide:

**Inputs**

- `seed: int` — episode-level seed
- `scenario: dict` — scenario pack parameters
- `ruleset: dict` — rule parameters/version; may be empty
- `agents: list[AgentId]` — player identities

**Methods**

| Method | Signature | Notes |
|--------|-----------|-------|
| `initial_state` | `(seed, scenario, ruleset, agents) -> State` | |
| `legal_actions` | `(state, agent_id) -> list[Action]` | Must be pure w.r.t. state. |
| `apply_action` | `(state, agent_id, action) -> TransitionResult` | `invalid` must be False if action came from `legal_actions`. |
| `is_terminal` | `(state) -> TerminalResult \| None` | |
| `observe` | `(state, agent_id) -> Observation` | Deterministic projection; must not mutate state. |
| `hash_state` | `(state) -> str` | Runner may own this; RuleSystem implementation must delegate to runner's canonical hash helper if so. |
| `serialize_state` | `(state) -> dict` | Must return a JSON-serializable dict. Floats are permitted; runner normalizes them. Non-serializable values are a configuration error (4.5). |
| `serialize_action` | `(action) -> dict` | |
| `action_key` | `(action) -> str` | Stable canonical string for this action's class. |

**TransitionResult**

```
next_state: State
events: list[dict]       # optional; for trace
skip_agent: AgentId | None  # signal runner to skip this agent's next turn
invalid: bool            # must be False if action was legal
error: str | None
```

**TerminalResult**

```
terminal: bool = True
reason: str              # must be from vocabulary in Section 4.4
winners: list[AgentId]   # empty for draw/deadlock/timeout
scores: dict[AgentId, float] | None
```

**Purity requirement:** RuleSystem methods used for decision-making (`observe`, `legal_actions`, `is_terminal`, `hash_state`) may be invoked more than once per turn by the runner for validation or debugging. Behavior must be identical across invocations given the same state. Implementations must not rely on mutable internal caching or side effects.

**TerminalResult note:** `TerminalResult` carries only the fields defined above. Implementation-specific details such as `deadlock_agent` are recorded in anomaly evidence and trace events, not in `TerminalResult`.

Given identical inputs (scenario, ruleset, seeds, strategies), `apply_action` must be deterministic. `hash_state` must be stable and collision-resistant enough for practical cycle detection.

### 5.2 Strategy Contract

A Strategy is:

```
select_action(observation, legal_actions, rng, context) -> Action
```

`rng` is deterministic and derived from episode seed, step number, and agent id (see Section 6.2). Strategy must not inspect global state except through observation (enforced socially in v0).

**Strategies provided in v0:**

- `random_uniform` — selects uniformly from legal_actions using deterministic rng
- `greedy_heuristic` — scenario pack may define a heuristic hook; selects highest-scoring legal action
- `scripted` — sequence or rule-based; used to inject illegal actions in Toy 5
- `mixed` — weighted blend of strategies

---

## 6. Simulation Runner

### 6.1 Episode Execution Algorithm

```
Inputs:
  episode_seed, max_steps, rulesystem, strategies, scenario, ruleset, illegal_action_policy

state = initial_state(seed, scenario, ruleset, agents)
seen_digests = {hash_state(state): 0}  # record initial state at step_index=0
step_index = 0
pending_skips = set()

while step_index < max_steps:
  for agent in turn_order (from scenario config):

    terminal_result = is_terminal(state)
    if terminal_result: break

    if agent in pending_skips:
      pending_skips.remove(agent)
      step_index += 1
      continue

    legal = legal_actions(state, agent)

    if legal == []:
      record anomaly: deadlock(agent_id=agent, step_index=step_index, state_digest=hash_state(state))
      terminate(reason="deadlock")
      break

    obs = observe(state, agent)           # same state snapshot as legal_actions call
    action = strategy.select_action(obs, legal, rng, context)

    if canonical_json(serialize_action(action)) not in {canonical_json(serialize_action(a)) for a in legal}:
      record anomaly: illegal_action_attempt(agent_id=agent, step_index=step_index,
                                             action_key=action_key(action),
                                             attempted_action_cjson=canonical_json(serialize_action(action)),
                                             legal_action_keys=[action_key(a) for a in legal])
      if policy == "terminal_invalid_action":
        terminate(reason="invalid_action")
        break
      else:  # substitute_first
        action = legal[0]

    digest_before = hash_state(state)
    tr = apply_action(state, agent, action)
    state = tr.next_state

    if tr.skip_agent:
      pending_skips.add(tr.skip_agent)  # collapses duplicates via set

    digest_after = hash_state(state)
    append trace event: {step_index, agent_id=agent, action_key=action_key(action),
                         state_digest_before=digest_before, state_digest_after=digest_after}

    if digest_after in seen_digests:
      terminate(reason="cycle_detected",
                cycle_entry_step=seen_digests[digest_after],
                cycle_length=step_index - seen_digests[digest_after])
      break
    seen_digests[digest_after] = step_index

    step_index += 1
    run detectors incrementally

  if terminal: break

if not terminal:
  terminate(reason="timeout")
```

### 6.2 Deterministic RNG

```
episode_rng_seed   = H(run_seed, episode_index)
agent_step_seed    = H(episode_rng_seed, agent_id, step_index)
```

H is any stable hash; must be documented and fixed per run config version. `random_uniform` strategy uses `rng.randrange(len(legal_actions))` from a deterministic RNG instance seeded as above.

---

## 7. Detectors

Detectors are pure functions consuming transitions and producing flags with evidence. They run incrementally after each transition.

### 7.1 Deadlock Detector

Triggers when the current scheduled agent has `legal_actions == []`. Other agents having legal actions does not prevent deadlock; the runner does not reschedule.

Evidence: `state_digest`, `agent_id`, `step_index`.

### 7.2 Cycle / Infinite Loop Detector

Maintains a per-episode map of `state_digest -> first_step_seen`. Triggers if any previously seen digest repeats. Records `cycle_entry_step` and `cycle_length`. Terminates the episode (see Section 4.7).

Evidence: list of state digests around the loop (bounded), step indices.

### 7.3 Dominance / Degenerate Choice Hints

Stats-only flags (not game-theory):

- An `action_key` selected above threshold X% when alternatives (other legal action_keys) exist.
- An `action_key` used below threshold Y% across all episodes.
- First-player win-rate above threshold Z (default 0.7; configurable).

Thresholds are global defaults in workload config, overridable in input config.

Evidence: aggregated counts, sample episode IDs showing extreme behavior.

### 7.4 Timeout Detector

Terminal reason `timeout` when max_steps reached without prior terminal condition.

### 7.5 Illegal Action Detector

Fires whenever a strategy returns an action not in `legal_actions`. Records the full evidence regardless of policy (anomaly is always written even if the episode continues).

Evidence: `agent_id`, `step_index`, `action_key` attempted, `attempted_action_cjson` (canonical JSON of `serialize_action` of the attempted action), `legal_action_keys` at that step.

---

## 8. Metrics

### Episode-level

- winner(s), terminal reason, steps taken
- per-agent action_key counts
- per-agent score (optional)
- anomaly flags

### Run-level aggregates

- win-rate per agent position
- terminal reason distribution
- avg/median steps
- action_key usage histogram (global + per agent)
- anomaly incidence rates (cycle, deadlock, illegal_action)
- `illegal_action_rate` across episodes
- "top suspicious episodes" list (ranked by anomaly severity)

---

## 9. Artifact Bundle

### Layout

```
workspace/<profile>/rulesim/run/<run_id>/
  run.json                 # canonical resolved run config (schema_version included)
  summary.json             # aggregate metrics + anomalies (canonical JSON, sortable)
  probes/
    <probe_id>/
      summary.json
      episodes.csv         # one row per episode: terminal, steps, flags
  episodes/
    <episode_id>/
      episode.json         # episode config + terminal result
      trace.jsonl          # (optional) step events
      states/              # (optional) snapshots
  suspicious/
    index.json             # pointers to top suspicious episodes
```

### Run and Episode IDs

- `run_id`: ULID — path uniqueness, not content-addressed.
- `run_digest`: SHA-256 of canonical `run.json` (sorted keys, compact separators) — used for determinism verification.
- `run_id` is excluded from `run_digest`.

### Trace Event Schema (minimum per step)

```json
{
  "step_index": 0,
  "agent_id": "agent_0",
  "action_key": "pass",
  "state_digest_before": "...",
  "state_digest_after": "...",
  "terminal": null
}
```

### Canonical JSON Rules

All artifact JSON files must use sorted keys, compact separators, no trailing whitespace, and floats rounded to 6 significant figures. This is required for digest reproducibility.

### Artifact Write Policy

| Policy | What is written |
|--------|----------------|
| `none` | `run.json`, `summary.json`, probe summaries only |
| `suspicious_only` | Above + trace for episodes in `suspicious/index.json` |
| `all` | Full trace for every episode (expensive) |

Suspicion ranking function (v0): cycle_detected > deadlock > illegal_action_attempt > timeout > dominance_hint. Ties broken by step count (shorter episodes rank higher as more exploitable).

---

## 10. Probing & Mutation Seam

v0 includes a minimal seam for audit mode without requiring a refactor.

A ProbePlan may vary:

- episode seeds
- strategy params
- scenario params
- ruleset params (optional)
- `illegal_action_policy`

Each probe record:

```
probe_id: str
variant_overrides: dict   # partial; merged into base config
episode_count: int
selection_policy: str | None
```

v0 requirement: probes are configuration-level only. No AST rule mutation needed yet.

---

## 11. CLI / Workload Surface

**Workload ID:** `rulesim_v0`

**Example invocation:**

```
orket run_workload rulesim_v0 --input <config.json> --workspace <path>
```

**Input Config Schema**

Required:
- `rulesystem_id: str`
- `run_seed: int`
- `episodes: int`
- `max_steps: int`
- `agents: list` — each: `{id, strategy, params}`
- `scenario: dict` — must include `turn_order: list[AgentId]`

Optional:
- `ruleset: dict`
- `illegal_action_policy: "substitute_first" | "terminal_invalid_action"` (default: `substitute_first`)
- `probes: list[ProbePlan]`
- `artifact_policy: "none" | "suspicious_only" | "all"` (default: `suspicious_only`)
- `detector_thresholds: {dominance_action_pct, underuse_action_pct, first_player_win_rate_threshold}`
- `schema_version: str`

**Output:** `result.json`

```json
{
  "run_id": "...",
  "run_digest": "...",
  "artifact_root": "...",
  "summary_digest": "...",
  "top_findings": [...]
}
```

---

## 12. Implementation Sequence (v0)

This sequence is normative, not advisory. It reflects dependency order: each step assumes the prior steps' invariants are frozen.

1. **Toy 1 (loop)** — locks cycle detector termination priority and `cycle_detected` terminal reason.
2. **Toy 2 (deadlock)** — locks deadlock detection, multi-agent scheduling, `deadlock` terminal reason.
3. **Toy 5 (illegal_action)** — locks illegal action policy seam, `illegal_action_attempt` anomaly shape.
4. **Toy 4 (golden_determinism)** — locks artifact digest harness and canonical JSON rules.
5. **Toy 3 (biased_first_player)** — locks dominance metrics and skew thresholds (depends on frozen `action_key` and "alternatives exist" semantics from prior toys).

---

## 13. Test Plan

### Toy 1: `loop`

**Purpose:** Locks cycle detector.

- 1 agent, 1 action: `action_key="advance"`
- State: `{tick: int}`. `apply_action` → `{tick: (tick + 1) % 2}`
- `is_terminal` always returns None

**Assertions:**
- `terminal_result.reason == "cycle_detected"`
- Anomaly contains `cycle_length=2`, `cycle_entry_step=0`
- Identical across two runs (determinism)

### Toy 2: `deadlock`

**Purpose:** Locks deadlock detection and scheduling interaction.

- 2 agents: `agent_0`, `agent_1`. `turn_order: [agent_0, agent_1]`
- `legal_actions(agent_0)` → `[pass]`; `legal_actions(agent_1)` → `[]`

**Assertions:**
- `terminal_result.reason == "deadlock"`
- `terminal_result.winners == []`
- Anomaly contains `agent_id="agent_1"`, `step_index=1` (agent_1 is second in turn_order; step_index increments per agent attempt), state digest

### Toy 3: `biased_first_player`

**Purpose:** Locks dominance/skew metrics. Build last.

- 2 agents, 2-phase structure: agent_0 may `win` or `pass`; if pass, agent_1 always `win`s
- Greedy run: agent_0 always wins → dominance + skew flags
- Random run (1000 episodes, fixed seed): agent_0 win-rate in `[0.45, 0.55]` → no flags

**Assertions (greedy):**
- `summary.win_rate["agent_0"] == 1.0`
- Dominance hint fires for `agent_0`/`win`
- First-player skew flag fires (threshold 0.7)

**Assertions (random):**
- Win-rate within tolerance
- No dominance or skew flags

### Toy 4: `golden_determinism`

**Purpose:** Snapshot test — summary digest stable across runs and environments.

- Fixed: `run_seed=42`, `episodes=100`, `max_steps=10`, `strategy=random_uniform`
- Capture `sha256(summary.json)` — check into repo
- CI asserts digest matches

### Toy 5: `illegal_action`

**Purpose:** Locks illegal action policy seam.

- 1 agent, legal actions: `[pass, move]`
- `scripted` strategy always proposes `illegal_move`
- Policy: `substitute_first`

**Assertions:**
- Episode completes
- Anomaly `illegal_action_attempt` present with full evidence
- Substituted action is `legal_actions[0]` (`pass`)
- `summary.illegal_action_rate` computed

---

## 14. Extension Integration

RuleSystems ship as extensions (or builtins) implementing the RuleSystem contract. Discovery via extension manager catalog using `rulesystem_id`. Extension exposes: `rulesystem_id`, `version`, entrypoint to instantiate the RuleSystem.

In-tree toy RuleSystems live under `orket/rulesim/toys/` and serve as contract fixtures for the runner. The extension interface is frozen after the toy suite passes.

---

## 15. Acceptance Criteria

**Determinism:** Running the same config twice produces identical `summary.json` digest, episode terminal outcomes, and anomaly flags. Artifact filenames may include `run_id`; content must match.

**Detectors:** Cycle detection catches Toy 1. Deadlock detection triggers on Toy 2. Illegal action anomaly fires on Toy 5.

**Metrics:** Win-rate distribution computed. Action_key usage histogram computed. `illegal_action_rate` computed.

**Artifacts:** All referenced episode IDs exist. `suspicious/index.json` points to real episodes. `run.json` includes `schema_version`.

---

## 16. Non-Goals / Guardrails

- This is not a game engine.
- This does not attempt to solve the meta.
- This does not require LLMs in v0.
- LLMs may be introduced in v1 for probe generation, finding summarization, or rule fix suggestions — but the substrate must stand without them.

---

## 17. v0 → v1 Extensions (not required now)

- Rule mutation engine (structural rule fuzzing, param sweeps, action-space mutations).
- Strategy library upgrades (MCTS, CFR-lite, bandits).
- Counterexample minimization ("smallest exploit trace").
- Differential testing across ruleset versions.
- Coverage metrics over rule graph / state graph.
- Pluggable finding format for human reports.
- Simultaneous move and interrupt scheduling models.
- Partial observability / information asymmetry policy.