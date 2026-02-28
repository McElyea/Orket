# Orket Reforger Layer 0 - PR Plan

Date: 2026-02-28  
Scope: Execute Layer 0 requirements in small, reviewable slices with deterministic contracts first.

## Planning Principles

- Preserve locked contracts from `01-REQUIREMENTS.md`.
- Keep each PR independently testable.
- Add deterministic ordering and digest capture early.
- Treat external optimizer/evaluator integrations as adapters, never core dependencies.

## PR1: Pack + Mode Schema + Validation

Objective: establish pack/mode contracts and deterministic resolution.

Changes:

- Add `orket/reforger/packs.py`:
  - load pack
  - validate required files
  - resolve inheritance overlays deterministically
- Add `orket/reforger/modes.py`:
  - parse and validate mode YAML schema
  - resolve suite reference
- Add foundational models/types in `orket/reforger/manifest.py` (or equivalent shared schema module).
- Add tests:
  - inheritance precedence determinism
  - required-file failure behavior
  - mode schema validation failures/success

Exit criteria:

- Resolved pack output is deterministic for the same inputs.
- Validation errors are stable and reproducible.

## PR2: Run Bundle Writer + Digests + Summary (Stubbed Eval)

Objective: implement deterministic artifact skeleton and one-screen summary.

Changes:

- Add `orket/reforger/runbundle.py`:
  - create run folder layout
  - write `manifest.json`
  - compute/store digests for inputs/outputs
- Add `orket/reforger/report/summary.py`:
  - generate `summary.txt` with required sections
- Add deterministic file writing helpers (sorted serialization).
- Add tests:
  - required bundle files exist
  - digest fields present
  - deterministic outputs across repeated runs (allow timestamp-field exclusions)

Exit criteria:

- Run bundle contract from requirements is satisfied with stub eval payloads.
- `summary.txt` format is stable and bounded.

## PR3: Eval Harness Interface + Stub Runner + Normalization

Objective: standardize evaluation boundary and normalized result shape.

Changes:

- Add `orket/reforger/eval/base.py` protocol definitions:
  - `EvalHarness`
  - `EvalResult`
- Add `orket/reforger/eval/runner.py` for orchestration.
- Add `orket/reforger/eval/parsers.py` for normalization.
- Add `orket/reforger/report/diff.py`:
  - baseline vs candidate regression/fix tracking
  - `best_vs_baseline.md`
- Generate `eval/scoreboard.csv` and candidate reports.
- Add tests:
  - normalized report schema
  - hard/soft fail counting
  - stable scoreboard ordering

Exit criteria:

- End-to-end pipeline can evaluate candidates via stub harness and emit normalized artifacts.

## PR4: Optimizer Abstraction + Built-in noop/mutate

Objective: make candidate generation pluggable while shipping deterministic built-ins.

Changes:

- Add `orket/reforger/optimizer/base.py` protocol:
  - `Optimizer.generate(...) -> list[Path]`
- Add `orket/reforger/optimizer/noop.py`.
- Add `orket/reforger/optimizer/mutate.py`:
  - deterministic mutation selection from `(seed, i)`
  - bounded token deltas
  - forbidden-pattern guardrails
  - per-candidate `mutation.json`
- Add tests:
  - candidate ordering and IDs stable
  - mutation metadata completeness
  - forbidden pattern protection

Exit criteria:

- `budget=N` yields deterministic candidate set and metadata.

## PR5: CLI Surface + Workflow Commands

Objective: expose Layer 0 workflows via `orket reforge ...`.

Changes:

- Add `orket/reforger/cli.py` with commands:
  - `run`
  - `init`
  - `open last` (best effort)
- Integrate `orket reforge` command group into existing CLI entrypoint.
- Implement exit-code contract:
  - `0` when hard constraints pass
  - `1` when any hard constraint fails
- Add tests:
  - CLI argument validation
  - run exit-code gate behavior
  - init path/metadata generation
  - open-last non-fatal failure behavior

Exit criteria:

- Terminal-only workflow is usable end-to-end with required command contracts.

## PR6 (Optional): External Eval Adapter

Objective: support real external evaluator tools without changing core contracts.

Changes:

- Adapter that shells to installed external tool (for example promptfoo).
- Parse and normalize external outputs to internal `EvalResult`.
- Graceful fallback to stub harness when external tool unavailable.
- Add tests:
  - fallback behavior
  - parser stability against expected external report fixtures

Exit criteria:

- Optional adapter path is available and isolated behind the eval interface.

## Cross-PR Test Matrix

Run continuously as PRs land:

- deterministic rerun snapshot checks
- bundle completeness checks
- inheritance and mode schema checks
- CLI command contract checks

## Risks and Mitigations

- Risk: non-deterministic filesystem traversal.
  - Mitigation: explicit path sorting and canonical serialization everywhere.
- Risk: unstable external evaluator output.
  - Mitigation: strict normalization layer and fixture-driven parser tests.
- Risk: mutation drift beyond intended bounds.
  - Mitigation: enforce token delta limits and mutation metadata auditing.

## Definition of Done (Layer 0)

- `orket reforge run` writes deterministic run bundle and prints `summary.txt`.
- `orket reforge init` scaffolds model+mode pack from base.
- pack inheritance and validation pass contract tests.
- determinism tests pass for fixed seed/input.
- optimizer and eval abstractions are in place with bundled noop/mutate + stub eval.
