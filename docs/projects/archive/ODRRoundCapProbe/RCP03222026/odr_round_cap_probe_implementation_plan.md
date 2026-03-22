# ODR Round-Cap Probe Implementation Plan

Last updated: 2026-03-22
Status: Archived
Owner: Orket Core

Background authority:

1. `docs/projects/archive/ODRLoopShapeHardening/LSH03222026/Closeout.md`
2. `docs/projects/archive/ODRRoleFitFollowup/RFU03222026/Closeout.md`
3. `docs/projects/archive/ODRModelRoleFit/MRF03212026/Closeout.md`
4. `docs/projects/archive/ContextContinuity/CC03212026/Closeout.md`

## Objective

Run a bounded `20`-round ceiling probe on only the previously observed `MAX_ROUNDS` ODR cases so Orket can determine whether those runs still make material progress beyond the archived `5` and `9` round budgets or whether they flatline earlier and do not justify a higher round cap.

## Scope Lock

1. This lane is a bounded priority override ahead of the other current roadmap items.
2. Do not relitigate continuity or reopen broad model-matrix expansion here.
3. Probe only exact scenario-run cases that previously stopped with `MAX_ROUNDS` in active roadmap evidence.
4. Keep execution serial only.
5. Freeze the probe budget at `20`.
6. Reuse the same pair behavior, continuity mode, and prompt policy that produced the source `MAX_ROUNDS` result for each rerun.
7. Emit inspectability, compare, verdict, and closeout artifacts in `benchmarks/staging/`.

## Proposed Execution Slices

### RCP-IMP-00: Probe Freeze

Objective:

1. freeze the exact probe set, source artifacts, and `20`-round budget in machine-readable form,
2. place the lane at the top of the roadmap while the probe is active.

### RCP-IMP-01: Targeted Probe Runner

Objective:

1. rerun only the frozen `MAX_ROUNDS` cases,
2. preserve the source pair and source prompt/continuity policy for each case,
3. compute where requirement movement stops materially changing.

### RCP-IMP-02: Live Ceiling Probe

Objective:

1. run the frozen probe set live at `20` rounds,
2. record whether each case still stops by `MAX_ROUNDS`, exits earlier for another stop reason, or flatlines before the cap.

## Success Criteria

The lane is complete only when:

1. the top-priority probe lane is frozen in machine-readable form,
2. the `20`-round reruns have been executed for every frozen `MAX_ROUNDS` source case,
3. the verdict artifact can state whether the round cap still appears binding for each probe or whether the run flatlined before the cap,
4. the lane records whether a higher round cap is justified for any active ODR lane.

## Current Execution Status

1. `RCP-IMP-00` is completed. The active-roadmap `MAX_ROUNDS` rerun set is frozen in [odr_round_cap_probe_lane_config.json](docs/projects/archive/ODRRoundCapProbe/RCP03222026/odr_round_cap_probe_lane_config.json) and [odr_round_cap_probe_registry.json](docs/projects/archive/ODRRoundCapProbe/RCP03222026/odr_round_cap_probe_registry.json).
2. `RCP-IMP-01` is completed. The serial probe runner preserves the source pair, source continuity mode, and any source loop hardening policy for each rerun, then records movement analysis from the emitted inspectability artifacts.
3. `RCP-IMP-02` is completed. The `20`-round live probe shows one real budget effect and two non-budget failures:
   1. `Command-R:35B -> gemma3:27b / missing_constraint_resolved` no longer dies on `MAX_ROUNDS`; it reaches `STABLE_DIFF_FLOOR` and converges in `9` rounds, so the source `5`-round cap was too low for that case.
   2. `mistralai/magistral-small-2509 -> gemma3:27b / missing_constraint_resolved` fails immediately with `CODE_LEAK`, so raising the round cap does not help.
   3. `mistralai/magistral-small-2509 -> gemma3:27b / overfitting` keeps changing until round `18` but exits on `FORMAT_VIOLATION`, not `MAX_ROUNDS`, so `20` rounds do not justify a higher cap by themselves.
4. The current bounded answer is: a higher cap can rescue some `5`-round truncations, but the probe does not support raising the general ODR round cap to `20`.
