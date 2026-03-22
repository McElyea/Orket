# RCP03222026 Closeout

Last updated: 2026-03-22
Status: Archived
Owner: Orket Core

## Scope

This lane ran a bounded `20`-round ceiling probe on only the active-roadmap ODR cases that had previously stopped with `MAX_ROUNDS`.

Primary closure areas:

1. frozen `20`-round probe set,
2. source-policy-preserving reruns,
3. inspectability, compare, verdict, and closeout artifacts,
4. explicit answer on whether raising the general ODR round cap is justified.

## Completion Gate Outcome

The lane completion gates are satisfied:

1. the probe set was frozen in machine-readable form,
2. every frozen `MAX_ROUNDS` source case was rerun at `20` rounds,
3. the verdict artifact states whether the round cap still appears binding for each probe,
4. the lane records whether a higher general ODR round cap is justified,
5. roadmap and project-index cleanup were completed in the same closeout change.

## Outcome

The lane closed with a bounded negative result on the general round-cap question.

1. The probe does not support raising the general ODR round cap to `20`.
2. `Command-R:35B -> gemma3:27b / missing_constraint_resolved` showed a real budget effect: the earlier `5`-round cap was too low, and the run converged by `9` rounds with `STABLE_DIFF_FLOOR`.
3. `mistralai/magistral-small-2509 -> gemma3:27b / missing_constraint_resolved` did not need more rounds; it failed immediately with `CODE_LEAK`.
4. `mistralai/magistral-small-2509 -> gemma3:27b / overfitting` kept changing until round `18` but exited on `FORMAT_VIOLATION`, not `MAX_ROUNDS`.
5. The correct bounded conclusion is narrower than “rounds never matter”: some `5`-round truncations can be too tight, but the current evidence does not justify a general increase to `20`.

## Verification

Observed path: `primary`
Observed result: `success`

Structural proof:

1. `python -m pytest -q tests/scripts/test_round_cap_probe.py`

Live proof:

1. `ORKET_DISABLE_SANDBOX=1 python scripts/odr/prepare_odr_round_cap_probe.py`
2. Canonical staging outputs:
   1. [benchmarks/staging/odr/round_cap_probe/odr_round_cap_probe_bootstrap.json](benchmarks/staging/odr/round_cap_probe/odr_round_cap_probe_bootstrap.json)
   2. [benchmarks/staging/odr/round_cap_probe/odr_round_cap_probe_inspectability.json](benchmarks/staging/odr/round_cap_probe/odr_round_cap_probe_inspectability.json)
   3. [benchmarks/staging/odr/round_cap_probe/odr_round_cap_probe_compare.json](benchmarks/staging/odr/round_cap_probe/odr_round_cap_probe_compare.json)
   4. [benchmarks/staging/odr/round_cap_probe/odr_round_cap_probe_verdict.json](benchmarks/staging/odr/round_cap_probe/odr_round_cap_probe_verdict.json)
   5. [benchmarks/staging/odr/round_cap_probe/odr_round_cap_probe_closeout.json](benchmarks/staging/odr/round_cap_probe/odr_round_cap_probe_closeout.json)

Governance proof:

1. `python scripts/governance/sync_published_index.py --index benchmarks/staging/index.json --readme benchmarks/staging/README.md --write`
2. `python scripts/governance/sync_published_index.py --index benchmarks/staging/index.json --readme benchmarks/staging/README.md --check`
3. `python scripts/governance/check_docs_project_hygiene.py`

## Not Fully Verified

1. This lane does not prove that `5` and `9` are globally optimal round caps.
2. The result is bounded to the specific active-roadmap cases, models, providers, and `v1_compiled_shared_state` substrate used here.
3. The canonical evidence remains staging-only and is not published evidence.

## Archived Documents

1. [docs/projects/archive/ODRRoundCapProbe/RCP03222026/odr_round_cap_probe_implementation_plan.md](docs/projects/archive/ODRRoundCapProbe/RCP03222026/odr_round_cap_probe_implementation_plan.md)
2. [docs/projects/archive/ODRRoundCapProbe/RCP03222026/odr_round_cap_probe_lane_config.json](docs/projects/archive/ODRRoundCapProbe/RCP03222026/odr_round_cap_probe_lane_config.json)
3. [docs/projects/archive/ODRRoundCapProbe/RCP03222026/odr_round_cap_probe_registry.json](docs/projects/archive/ODRRoundCapProbe/RCP03222026/odr_round_cap_probe_registry.json)
4. [docs/projects/archive/ODRRoundCapProbe/RCP03222026/odr_round_cap_probe_output_schema.json](docs/projects/archive/ODRRoundCapProbe/RCP03222026/odr_round_cap_probe_output_schema.json)

## Residual Risk

1. The probe shows one case where `5` rounds was too low, so future loop-shape work should not treat `5` as a universal ceiling.
2. Any new round-cap experiment must reopen as a new explicit roadmap lane rather than quietly modifying this archived authority.
