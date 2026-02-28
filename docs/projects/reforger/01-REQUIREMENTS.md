# Orket Reforger Framework v0 (Layer 0) - Requirements

Date: 2026-02-28  
Status: draft-for-requirements  
Owner: Orket (core framework, not an extension)  
Scope: Terminal-first role/archetype/persona reforging with deterministic run bundles; off-the-shelf optimizers optional.

## 0. Intent

Build a Reforger Framework that can automatically iterate on persona/role/archetype prompt packs against a scenario constraint sheet, producing deterministic, diffable artifacts and a one-screen terminal summary.

Success criteria:

- Repeatable evaluation across models and scenario modes.
- Stable run bundle artifacts (diffable, replayable).
- Clear CLI experience with no UI required.
- Ability to swap optimizers (PromptWizard / DSPy / TextGrad / simple mutate) without changing evaluation.

## 1. Definitions

### 1.1 Reforge Pack

A pack is a directory containing prompt components and metadata.

Minimum contents:

- `pack.json` (metadata, version, inheritance)
- `system.txt` or `system.md`
- `developer.txt` (optional)
- `examples.jsonl` (optional few-shot examples)
- `constraints.yaml` (resolved constraint sheet snapshot used to build/evaluate)

Pack inheritance:

- A pack may declare `extends: <pack_id>`.
- Overlays are merged with deterministic precedence.
- A resolved pack is the merged inheritance result.

### 1.2 Scenario Mode

A mode is a named constraint set, defined by `modes/<mode_id>.yaml`.

Examples:

- `truth_or_refuse`
- `lies_only`
- `liar_riddle`

### 1.3 Tier-0 Model Set

Only 3 models must be supported-for-forging initially (chosen locally by user).  
All other models are supported through `init/clone from closest tier-0 pack`.

### 1.4 Run Bundle

Every reforge run must produce a deterministic folder with:

- inputs (manifest, resolved pack)
- generated candidates
- evaluation reports
- diffs vs baseline
- `summary.txt` for CLI

Bundle content must be stable across reruns with the same seed and inputs.

## 2. Non-Goals (Layer 0)

- No UI beyond terminal output.
- No requirement to implement optimization algorithms internally.
- No live web access.
- No magic model reasoning.
- No TextMystery-specific coupling.

## 3. Core Contracts (Locked)

### 3.1 CLI Commands (Minimum)

`orket reforge run`

- Full generate -> evaluate pipeline.
- Required flags:
  - `--mode <mode_id>`
  - `--model <model_id>`
  - `--seed <int>`
  - `--budget <int>`
  - `--baseline <pack_id|path>` (optional; default current best for model+mode if present)
  - `--out <dir>` (optional; default run bundle location)
- Output: prints `summary.txt`.
- Exit code:
  - `0` if all hard constraints pass.
  - `1` if any hard constraint fails (even if best candidate exists).

`orket reforge init`

- Creates a new model+mode pack inheriting from a base pack.
- Required flags:
  - `--mode <mode_id>`
  - `--model <model_id>`
  - `--from <pack_id|path>`

`orket reforge open last`

- Best-effort command to open last run bundle markdown report(s).
- Failure to open is non-fatal.

### 3.2 Deterministic Artifact Requirements

Given identical:

- mode file contents
- baseline pack contents
- scenario suite
- model id + captured model interface version string
- seed + budget

Then:

- candidate ordering, selection, and evaluation reports are deterministic
- run bundle includes digests for all inputs and outputs

### 3.3 One-Screen Terminal Summary (Required)

`summary.txt` must include:

- run header (timestamp, seed, model, mode, budget)
- best candidate pack id
- top-N scoreboard (default N=5)
- delta vs baseline (fixed/regressed/unchanged counts)
- bounded failure triage:
  - top 5 new failures
  - top 5 frequent failures
  - top 5 most severe failures
- hard-constraint gate status:
  - PASS/FAIL and count of hard violations

### 3.4 Evaluation Harness Abstraction

The framework must support a pluggable evaluation harness.

Minimum interface:

```python
class EvalHarness(Protocol):
    def run(
        self,
        *,
        model_id: str,
        mode_id: str,
        pack_path: Path,
        suite_path: Path,
        out_dir: Path,
    ) -> "EvalResult":
        ...
```

`EvalResult` must contain:

- summary metrics (`score`, `hard_fail_count`, `soft_fail_count`)
- list of failing case IDs with severity
- paths to generated reports (`json` + `md`)

Note: shelling out to external tools (for example `promptfoo`) is allowed; Orket must normalize external outputs.

### 3.5 Optimizer Abstraction (Scaffold in Layer 0)

Minimum interface:

```python
class Optimizer(Protocol):
    def generate(
        self,
        *,
        baseline_pack: Path,
        mode: dict,
        seed: int,
        budget: int,
        out_dir: Path,
    ) -> list[Path]:
        ...
```

Layer 0 bundled optimizers:

- `noop` (returns baseline only)
- `mutate` (deterministic small edits; see section 6)

## 4. Directory Structure (Locked)

Core repo:

```text
orket/
  reforger/
    __init__.py
    cli.py
    manifest.py
    packs.py
    modes.py
    runbundle.py
    optimizer/
      base.py
      noop.py
      mutate.py
    eval/
      base.py
      runner.py
      parsers.py
    report/
      summary.py
      diff.py
    tests/
      ...
```

Workspace data layout:

```text
reforge/
  modes/
  packs/
    base/<mode_id>/
    model/<model_id>/<mode_id>/
  suites/
    <mode_id>/
      cases.jsonl
      rubric.yaml
  runs/
    <timestamp>_reforge/
```

## 5. Mode / Constraint Sheet Contract

`modes/<mode_id>.yaml` minimum fields:

- `mode_id: str`
- `description: str`
- `hard_rules: list[str]`
- `soft_rules: list[str]`
- `rubric: dict`
- `required_outputs: list[str]`
- `suite_ref: str`

Hard rules are gates (PASS/FAIL), not scored dimensions.

## 6. Minimal Built-In Optimizer: mutate

Purpose: keep the system working without external optimizer integration.

Rules:

- deterministic mutations from `(seed, i)` where `i` is candidate index
- bounded edits only; honor configurable max token deltas
- 3-6 mutation types maximum:
  - reorder bullet lists in `system.*`
  - insert short clarify/refusal stanza
  - vary example subset/ordering when examples exist
  - tighten/loosen style qualifiers
- must not introduce forbidden patterns (configurable)

Output:

- `candidates/0001_pack/...`
- each candidate includes `mutation.json` describing exact changes

## 7. Run Bundle Contract (Locked)

On `orket reforge run`, produce:

```text
runs/<ts>_reforge/
  manifest.json
  inputs/
    mode.yaml
    baseline_pack_resolved/
  candidates/
    0001_pack_resolved/
    0002_pack_resolved/
  eval/
    candidate_0001/
      report.json
      report.md
    scoreboard.csv
  diff/
    best_vs_baseline.md
  summary.txt
```

`manifest.json` must include:

- tool version
- seed, budget
- model id + model interface version string
- mode id + digest
- baseline pack digest
- suite digest
- timestamps

## 8. Evaluation Suite Format (Layer 0)

`cases.jsonl` minimum per-case fields:

- `case_id: str`
- `prompt: str` (or future multi-turn)
- `expectations` object:
  - `hard: list[...]`
  - `soft: list[...]`

`rubric.yaml` defines weighted scoring categories.

Harness output must include:

- per-case pass/fail + scores
- overall metrics

## 9. Testing Requirements

### 9.1 Determinism Tests (Mandatory)

Same run twice must produce identical:

- `summary.txt`
- `scoreboard.csv`
- `best_vs_baseline.md`
- `manifest.json` except timestamp fields
- stable candidate ordering

### 9.2 Artifact Completeness Tests

- run bundle has required files
- digests present
- each candidate has `mutation.json`

### 9.3 CLI Contract Tests

- `run` exit code reflects hard-failure gate
- `init` creates expected path + metadata
- `open last` is best-effort and non-crashing

### 9.4 Pack Inheritance Tests

- resolved pack equals base + overlay deterministically
- missing required files produce deterministic validation errors

## 10. Acceptance Criteria (Layer 0 Exit)

Layer 0 is complete when:

- `orket reforge run` produces run bundle + one-screen summary
- determinism tests pass
- pack inheritance works
- evaluation harness runs (stub evaluator acceptable at first)
- optimizer abstraction exists and mutate supports deterministic N candidates
- tier-0 workflow exists:
  - init from base
  - run evaluates and stores best per model+mode (optional index)

## 11. Suggested PR Slices

- PR1: pack/mode schema + validation + inheritance tests
- PR2: run bundle writer + digests + summary printer + determinism checks
- PR3: eval harness runner + normalized report + scoreboard/diff
- PR4: built-in deterministic mutate optimizer + integration
- PR5 (optional): external harness adapter + normalized mapping + fallback

## Notes for Implementation

- Treat this as a compiler-style pipeline:
  - inputs -> candidate generation -> evaluation -> reporting -> artifacts
- Keep terminal UI bounded to `summary.txt` triage sections.
- Enforce deterministic ordering everywhere:
  - sorted paths
  - stable candidate IDs
  - stable case ordering
- Do not encode lying as a boolean trait.
- Validate behavior with constraints + suites, not model-specific assumptions.
- Do not overfit to one model; prefer inheritance and config-driven adaptation.
