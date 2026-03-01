> **LOCKED: v0 semantics frozen. Changes to artifact of record, render classification, determinism boundary, or role contracts require a v1 label.**

---

# Orket UI Forge v0 — Specification
*Status: Lock candidate. All decisions herein are normative unless marked [advisory].*

---

## 0. Core Thesis

UI is not visuals. UI is a constrained projection of system state and allowed transitions.

Therefore: if Orket can refine system requirements deterministically, it can refine UI interface contracts deterministically.

UI Forge is not a UI builder. It is a governance lab for interface contracts.

---

## 1. Formal Definition

UI Forge is a structured multi-model refinement loop that produces and stabilizes interface contracts for a given system specification.

**Output is not:** JSX, HTML, screenshots, Figma files, or any rendered artifact.

**Output is:** a wireframe IR (machine-readable interface contract), a correctness report, and optionally a human-readable visual render classified as evidence.

---

## 2. Locked Decisions

The following decisions are normative for v0. Revisiting any of them is a v1 concern.

### U1. Artifact of Record

The wireframe IR (`wireframe_tree.json`) is the artifact of record. It is the canonical, diffable, digestable representation of UI Forge output. All governance, drift scoring, and acceptance criteria operate against the IR, not against any visual render.

### U2. Render Output Classification

Any visual render (PNG, SVG, PDF) is evidence, not truth. Renders are generated for human inspection only. They may be omitted or regenerated without affecting run correctness, digest stability, or governance outcomes.

### U3. Renderer Mode (v0)

UI Forge v0 operates in **B2: Illustrative Renderer Mode.**

- Renders are not used for snapshot testing.
- Render digests are not part of governance, drift scoring, or acceptance criteria.
- Cross-platform pixel stability is explicitly not a v0 requirement.

### U4. Determinism Boundary (v0)

Determinism requirements apply to:

- IR generation (spec → IR compiler)
- IR canonicalization and digesting
- Metrics and drift scoring computed over IR

Determinism does not apply to:

- Rasterization
- Font rendering
- Layout engine platform variance
- Any output classified as evidence

### U5. Upgrade Path (v1)

B1: Deterministic Renderer Mode is a v1 feature, gated by a renderer determinism harness:

- Pinned renderer version(s)
- Controlled font strategy
- CI matrix confirmation that identical IR produces stable render digests across platforms

Switching from B2 → B1 is a versioned contract change, not a silent enhancement.

### U6. UI Correctness Definition

Correctness in UI Forge is not aesthetic. It is structural. A UI spec is correct if:

- Every required system state field is represented in the IR (state coverage)
- Every UI action maps to exactly one declared state transition (action mapping)
- All required flows are reachable from the start node (reachability)
- Destructive actions carry confirmation affordances (guardrail invariants)
- Every failure state has a visible representation (error surfacing)

These properties are machine-checkable against the IR. None require a rendered artifact.

---

## 3. Artifact Object Model

### UIInterfaceSpec

The primary input to the refinement loop. Produced and revised by model roles across iterations.

```json
{
  "version": "0.1",
  "system_scope": "string",
  "state_exposure": [
    { "name": "string", "type": "string", "required": true }
  ],
  "actions": [
    { "name": "string", "preconditions": ["string"] }
  ],
  "invariants": ["string"],
  "ambiguities": ["string"]
}
```

### wireframe_tree.json (Wireframe IR)

The artifact of record. Compiled deterministically from UIInterfaceSpec. Contains:

- Component tree (nodes, types, hierarchy)
- State binding declarations (which state fields map to which nodes)
- Action binding declarations (which nodes trigger which actions)
- Reachability graph (flow adjacency)
- IR digest (SHA-256 of canonical IR JSON)

### ui_correctness_report.json

Produced by the correctness checker (no model involvement). Contains:

- Pass/fail per correctness dimension (U6)
- Invariant violations with evidence pointers
- State coverage gaps
- Unreachable nodes or flows
- Drift delta vs prior iteration

### Render artifact (evidence only)

Optional. SVG or PNG generated from wireframe IR for human inspection. Not digested. Not governed. Labeled with the IR digest that produced it so provenance is traceable.

---

## 4. Roles

### Role 1 — Architect

Proposes UIInterfaceSpec. Defines state exposure, user-visible transitions, required APIs, and component structure. Owns the initial proposal and revision responses.

### Role 2 — UX Challenger

Attacks the spec for: cognitive ambiguity, hidden state, misleading flows, unreachable required paths, and excessive surface area. Does not propose — only critiques and flags.

### Role 3 — Integrity Guard

Verifies structural correctness: invariant compliance, deterministic state mapping, action-to-mutation coverage, guardrail presence on destructive operations. Produces a pass/fail finding per correctness dimension.

### Role 4 — Minimalist [optional, v0]

Attempts to reduce unnecessary state exposure and API surface. Flags over-specification. May be omitted in early runs.

---

## 5. Refinement Loop

```
Inputs:
  system_spec, initial_ui_spec, max_iterations, stabilization_threshold, roles

For iteration in [0..max_iterations):

  Architect produces UIInterfaceSpec revision N

  Challenger produces critique (ambiguities, hidden state, flow gaps)

  Integrity Guard produces correctness finding (pass/fail per U6 dimension)

  Runner computes:
    IR from spec (deterministic compiler)
    IR digest
    drift_delta vs iteration N-1
    invariant_violation_count
    correctness_score

  If drift_delta < stabilization_threshold AND invariant_violation_count == 0:
    mark stable, break

  Store iteration artifact bundle

Surface top 3 specs by:
  1. Lowest invariant violation count
  2. Highest drift stability
  3. Minimal state exposure (API surface)
```

---

## 6. Scoring Dimensions

Scores are computed over the IR, not over renders.

| Dimension | What is measured |
|-----------|-----------------|
| Contract clarity | Explicit state definitions, explicit transition mapping, no implicit mutations |
| Deterministic mapping | Each UI action maps to exactly one state mutation |
| State coverage | All critical system invariants are visible in the IR |
| Drift stability | Does the IR stabilize across iterations, or oscillate? |
| API minimalism | State exposure and action surface are no larger than required |

---

## 7. Artifact Bundle

```
workspace/<profile>/ui_forge/run/<run_id>/
  run.json                    # canonical run config, schema_version included
  summary.json                # aggregate scores, drift, top 3 rankings
  iterations/
    <iteration_id>/
      ui_spec.json            # UIInterfaceSpec for this iteration
      wireframe_tree.json     # IR (artifact of record)
      ui_correctness_report.json
      render.svg              # [optional] evidence only, not governed
  top_3/
    index.json                # pointers to top 3 candidate iterations
    <rank_1|2|3>/
      wireframe_tree.json
      ui_correctness_report.json
      render.svg              # [optional]
```

Run and digest rules follow RuleSim conventions: `run_id` is ULID, `run_digest` is SHA-256 of canonical `run.json`, canonical JSON uses sorted keys and compact separators throughout.

---

## 8. Correctness Checks (No Model)

The following checks run deterministically against the IR with no model involvement:

- **State coverage:** every `state_exposure` field in UIInterfaceSpec appears in at least one IR node binding.
- **Action mapping:** every `actions` entry in UIInterfaceSpec maps to exactly one IR action binding.
- **Reachability:** all required flows are reachable from the IR start node.
- **Guardrail invariants:** destructive actions (flagged in spec) have confirmation affordances in IR.
- **Error surfacing:** every failure state in spec has a corresponding IR node.

Failures produce findings in `ui_correctness_report.json` with evidence pointers to the specific IR node or binding that failed.

---

## 9. Minimal First Experiment

Do not build a full system. Validate the loop first.

**System:** Orket runtime dashboard

**Question:** What must a dashboard expose to make runtime state safe and observable?

**Run:**
- 3 roles (Architect, Challenger, Integrity Guard)
- 5 iterations
- No rendering required
- IR output only

**Pass criteria:**
- Same input twice → same IR digest
- Drift scoring is stable by iteration 3–5
- Roles produce meaningfully different findings
- Correctness report exposes at least one non-obvious gap

If this works, the loop is real. If it doesn't stabilize, the problem is role prompt design or spec schema, not the substrate.

---

## 10. What This Is Not

- Not a UI builder
- Not a screenshot generator
- Not a design studio
- Not an aesthetic judgment system

It is: a governance lab for interface contracts. Models propose. Deterministic compiler proves. Artifacts are evidence of the contract, not the contract itself.

---

## 11. Relationship to RuleSim

UI Forge reuses the Orket refinement substrate without modification. The loop structure, artifact conventions, digest rules, and scoring model are direct extensions. The only new primitive is UIInterfaceSpec and the IR compiler.

UI correctness (U6) is to UI Forge what the terminal reason vocabulary is to RuleSim: the normative definition of what "correct" means in this domain.

---

## 12. v0 → v1 Extensions (not required now)

- B1: Deterministic Renderer Mode with render digest governance
- Accessibility invariants as a scored correctness dimension
- Event determinism constraints (user interaction → state mutation mapping)
- Multi-system scope (specs that span more than one system boundary)
- Automated counterexample minimization ("smallest ambiguous flow")