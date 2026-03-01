# RuleSim v0 Implementation Plan

Reference: [orket-rulesim-v0-spec.md](orket-rulesim-v0-spec.md)

---

## Overview

Greenfield package `orket/rulesim/` implementing the spec's simulation kernel, runner, detectors, metrics, strategies, artifact output, and five toy fixture tests. Follows the spec's normative build order (Section 12): each toy locks a contract before the next begins.

---

## Phase 0: Package Skeleton + Contracts

**Goal:** Establish the module layout and abstract contracts so everything after this has a place to land.

### Files to create

```
orket/rulesim/
  __init__.py
  contracts.py          # Protocol/ABC: RuleSystem, Strategy, TransitionResult, TerminalResult
  types.py              # AgentId, State, Action, Observation type aliases; config dataclasses
  canonical.py          # canonical_json(), hash_state(), float normalization (6 sig figs)
  runner.py             # EpisodeRunner (stub, filled in Phase 1)
  detectors.py          # Detector base + all detector implementations (stub)
  metrics.py            # Episode-level and run-level metric collectors (stub)
  strategies/
    __init__.py
    random_uniform.py
    greedy_heuristic.py
    scripted.py
    mixed.py
  artifacts.py          # Artifact bundle writer (stub)
  toys/
    __init__.py         # toy registry
    loop.py             # Toy 1
    deadlock.py         # Toy 2
    biased_first_player.py  # Toy 3
    golden_determinism.py   # Toy 4 (reuses a toy RuleSystem + golden hash)
    illegal_action.py       # Toy 5
tests/rulesim/
  __init__.py
  conftest.py           # shared fixtures (configs, seeds)
  test_toy1_loop.py
  test_toy2_deadlock.py
  test_toy3_biased.py
  test_toy4_golden.py
  test_toy5_illegal.py
  test_canonical.py     # unit tests for canonical_json, hash_state
```

### Deliverables

- `contracts.py`: `RuleSystem` (Protocol with all 9 methods from spec 5.1), `Strategy` (Protocol), `TransitionResult` and `TerminalResult` as frozen dataclasses.
- `types.py`: `AgentId = str`, config dataclasses (`RunConfig`, `ProbeConfig`, `AgentConfig`) matching spec Section 11 input schema. Pydantic or plain dataclasses -- plain dataclasses for now, Pydantic later if validation demands it.
- `canonical.py`: `canonical_json(obj) -> str` (sorted keys, compact separators, float normalization to 6 sig figs), `hash_state(state_dict) -> str` (SHA-256, truncated 16 hex chars). Unit-tested standalone.
- All stubs import cleanly, `pytest --collect-only` passes.

### Tests

- `test_canonical.py`: round-trip canonical JSON, float normalization edge cases, hash stability.

---

## Phase 1: Runner Core + Toy 1 (cycle detection)

**Locks:** cycle detector termination priority, `cycle_detected` terminal reason, step_index semantics, state digest map seeding.

### Implementation

1. **`runner.py` -- `run_episode()`**: Implement the full episode execution algorithm from spec Section 6.1. This is the heart.
   - Turn scheduling from `turn_order` config.
   - `step_index` increments per agent attempt (including skips).
   - `seen_digests` map seeded with initial state at `step_index=0`.
   - Cycle check after each transition.
   - Trace event recording.
   - `pending_skips` set for `skip_agent` handling.

2. **`detectors.py` -- `CycleDetector`**: Inline in the runner loop (spec says "fires after each state transition"). Records `cycle_entry_step`, `cycle_length`.

3. **`strategies/random_uniform.py`**: Deterministic RNG per spec 6.2. `H = hashlib.sha256(...)`, seed derivation from `(episode_rng_seed, agent_id, step_index)`.

4. **`toys/loop.py`**: 1 agent, 1 action (`advance`), state = `{tick: int}`, `apply_action` sets `tick = (tick + 1) % 2`. `is_terminal` always `None`.

### Tests

- `test_toy1_loop.py`:
  - Terminates with `reason="cycle_detected"`.
  - Anomaly has `cycle_length=2`, `cycle_entry_step=0`.
  - Two identical runs produce identical results.

---

## Phase 2: Toy 2 (deadlock)

**Locks:** deadlock detection, multi-agent scheduling, `deadlock` terminal reason.

### Implementation

1. **`detectors.py` -- `DeadlockDetector`**: Triggers when `legal_actions == []` for current scheduled agent. Evidence: `state_digest`, `agent_id`, `step_index`.

2. **`toys/deadlock.py`**: 2 agents, `turn_order: [agent_0, agent_1]`. `agent_0` has `[pass]`, `agent_1` has `[]`.

### Tests

- `test_toy2_deadlock.py`:
  - `reason="deadlock"`, `winners == []`.
  - Anomaly has `agent_id="agent_1"`, `step_index=1`.

---

## Phase 3: Toy 5 (illegal action)

**Locks:** illegal action policy seam, `illegal_action_attempt` anomaly shape, `substitute_first` behavior.

### Implementation

1. **Runner illegal action validation**: Before `apply_action`, check `canonical_json(serialize_action(action))` against legal set. Branch on policy.

2. **`detectors.py` -- `IllegalActionDetector`**: Records full evidence (`agent_id`, `step_index`, `action_key`, `attempted_action_cjson`, `legal_action_keys`).

3. **`strategies/scripted.py`**: Takes a sequence of actions to propose regardless of legality.

4. **`toys/illegal_action.py`**: 1 agent, legal `[pass, move]`, scripted strategy always proposes `illegal_move`.

### Tests

- `test_toy5_illegal.py`:
  - Episode completes (policy = `substitute_first`).
  - Anomaly `illegal_action_attempt` present with full evidence.
  - Substituted action is `pass` (= `legal_actions[0]`).
  - `illegal_action_rate` computed in summary.
  - Re-run with `terminal_invalid_action` policy: terminates with `reason="invalid_action"`.

---

## Phase 4: Toy 4 (golden determinism) + Artifacts

**Locks:** artifact digest harness, canonical JSON rules for all output files.

### Implementation

1. **`artifacts.py`**: Full artifact writer.
   - `run.json` (resolved config, `schema_version`).
   - `summary.json` (aggregate metrics, canonical JSON).
   - `episodes/` and `trace.jsonl` per artifact_policy.
   - `suspicious/index.json` with ranking (cycle > deadlock > illegal > timeout > dominance; ties by step count ascending).
   - ULID for `run_id`. SHA-256 of canonical `run.json` (excluding `run_id`) for `run_digest`.

2. **`metrics.py`**: Episode-level (winner, reason, steps, per-agent action counts, anomaly flags) and run-level (win-rate, terminal reason distribution, avg/median steps, action histogram, anomaly rates, `illegal_action_rate`, top suspicious).

3. **`run_batch()`** in runner: orchestrates N episodes, collects metrics, writes artifacts.

4. **`toys/golden_determinism.py`**: Uses an existing toy RuleSystem. Config: `run_seed=42, episodes=100, max_steps=10, strategy=random_uniform`. Golden `summary.json` digest checked into repo as a fixture.

### Tests

- `test_toy4_golden.py`:
  - `sha256(summary.json)` matches golden fixture.
  - Two runs produce identical digests.

---

## Phase 5: Toy 3 (biased first player) + Dominance Detector

**Locks:** dominance metrics, skew thresholds, `action_key` usage histograms.

### Implementation

1. **`detectors.py` -- `DominanceDetector`**: Stats flags for action overuse/underuse thresholds, first-player win-rate threshold (default 0.7). Evidence: aggregated counts, sample episode IDs.

2. **`toys/biased_first_player.py`**: 2 agents, 2-phase: `agent_0` can `win` or `pass`; if pass, `agent_1` always wins.

### Tests

- `test_toy3_biased.py`:
  - Greedy: `agent_0` win-rate = 1.0, dominance hint fires, first-player skew flag fires.
  - Random (1000 episodes, fixed seed): win-rate in `[0.45, 0.55]`, no flags.

---

## Phase 6: Probes, Workload Registration, CLI

**Goal:** Wire everything into the Orket workload system.

### Implementation

1. **Probe execution**: `ProbeConfig` applies `variant_overrides` (partial merge into base config), runs `episode_count` episodes, writes per-probe `summary.json` + `episodes.csv`.

2. **Workload entry point** -- `orket/rulesim/workload.py`:
   - `run_rulesim_v0(input_config, workspace_path) -> result.json`
   - Validates input config against schema.
   - Resolves `rulesystem_id` (in-tree toys or extension catalog).
   - Calls `run_batch()`, writes artifacts, returns `{run_id, run_digest, artifact_root, summary_digest, top_findings}`.

3. **Register in `orket/workloads/registry.py`**: Add `rulesim_v0` to the builtin workload dispatch.

4. **`strategies/greedy_heuristic.py`** and **`strategies/mixed.py`**: Fill remaining strategy stubs.

### Tests

- Probe override merging.
- Workload end-to-end: config in, `result.json` out, artifacts on disk.

---

## Phase 7: Polish + CI

1. **Timeout detector**: Ensure `reason="timeout"` fires when `max_steps` reached (should already work from Phase 1, just needs explicit test).
2. **skip_agent semantics**: Dedicated test (single-skip, idempotent collapse, skip-self-next-turn).
3. **State serialization validation** (spec 4.5): Test that non-JSON-serializable state values raise config error with key path.
4. **Type hints**: Full typing across all public APIs.
5. **CI fixture**: Golden digest in `tests/rulesim/fixtures/golden_summary_digest.txt`, asserted in `test_toy4_golden.py`.

---

## Dependency Graph

```
Phase 0 (skeleton)
  |
Phase 1 (runner + cycle)
  |
  +-- Phase 2 (deadlock)
  |
  +-- Phase 3 (illegal action)
        |
        Phase 4 (golden + artifacts)
              |
              Phase 5 (dominance)
                    |
                    Phase 6 (probes + workload)
                          |
                          Phase 7 (polish)
```

Phases 2 and 3 can run in parallel after Phase 1.

---

## Estimated Scope

| Phase | New files | New test files | Key risk |
|-------|-----------|---------------|----------|
| 0 | 12 | 1 | Getting canonical JSON float normalization right |
| 1 | 3 (fill stubs) | 1 | Runner loop correctness (the hard part) |
| 2 | 1 | 1 | None (simple) |
| 3 | 2 | 1 | Legality equality via canonical JSON comparison |
| 4 | 2 (fill stubs) | 1 | Golden digest stability across platforms |
| 5 | 2 (fill stubs) | 1 | Threshold tuning for biased test |
| 6 | 2 | 1 | Workload registry integration |
| 7 | 0 | 2 | None |

---

## Principles

- **Spec is law.** If the plan contradicts the spec, the spec wins.
- **Each phase ends with passing tests.** No moving forward with red.
- **No premature abstraction.** Strategies are plain functions/classes, not a plugin framework. Extension integration (spec Section 14) is Phase 6, not Phase 0.
- **Canonical JSON is load-bearing.** Get it right in Phase 0 and never touch it again.
