# Orket Code Stabilizer "The Marshaller"
## Project Delivery Engine - Requirements v0

## 0. Goal
Turn untrusted code proposals into test-passing, replayable, auditable project progress via deterministic validation, denial of illegal state, and ledgered artifacts, with a UI that shows exactly what happened.

## 1. North Star Behaviors
- No silent drift: every accepted change is captured as a diff with a reason and a digest.
- No illegal state: failing builds/tests never become canonical.
- Reproducible runs: given the same repo snapshot + run inputs, Orket replays the same validation steps and produces equivalent decisions.
- Human inspectability: you can answer "why did we accept this?" in under 30 seconds.

## 2. Core Concept
Models propose. Orket disposes.

Models never write code directly. They submit patch proposals. Orket:
- validates the proposal contract
- applies the patch to a workspace clone
- runs deterministic gates (build/tests/lint)
- computes diffs + metrics
- accepts/rejects
- records the entire attempt in a run ledger

## 3. v0 Scope
### 3.1 In scope
- Single repo workspace
- Patch proposals as unified diff (or structured patch ops)
- Deterministic validation pipeline
  - Stage 1: contract validation of proposal
  - Stage 2: patch apply + allowlist enforcement
  - Stage 3: build/compile gate
  - Stage 4: test gate
  - Stage 5: static gate (optional v0: formatting/lint)
- Run artifacts
  - canonical ledger entry per attempt
  - logs, diffs, test output, metrics
- UI
  - run browser
  - patch/attempt inspector
  - failure triage view

### 3.2 Out of scope (v0)
- Multi-repo
- Fully automated long-horizon agent planning
- Internet crawling / RAG
- Advanced merge conflict resolution
- IDE plugin

## 4. Locked Decisions (v0)
1. Canonical state after acceptance is a Git commit on a designated branch, plus artifact ledger.
2. Promotion authority in v0 is human-only (local user), explicitly triggered from UI/CLI.
3. Promotion is a separate ledgered event with actor metadata.
4. Execution envelope is required per run: `lockfile` or `container`.
5. Acceptance is pure gate pass/fail plus policy denies. Policy can deny, never override a failing gate to accept.
6. Determinism for v0 is logical equivalence via equivalence key; byte-for-byte parity is best-effort.
7. Ledger is append-only and tamper-evident via hash chain.
8. Flake handling is deny-by-default with bounded retries and explicit quarantine mode.
9. All attempts record explicit contract versions and policy version/digest.

## 5. Determinism and Canonicalization Rules (v0)
### 5.1 Run inputs must include non-determinism controls
- `seed`
- `model_id`
- `temperature` (fixed default)

### 5.2 Execution envelope
`execution_envelope.mode = lockfile | container`

If `lockfile`:
- lockfile required
- record `lockfile_digest`
- record interpreter + OS fingerprint + key tool versions
- determinism level is best-effort

If `container`:
- record `container_image_digest`
- recommended for strong determinism

### 5.3 Output canonicalization
- UTF-8
- canonical JSON key ordering (RFC8785-like minimum)
- newline `\n`
- no trailing whitespace
- workspace-relative paths only
- path comparison uses normalized `path_norm`
- timestamps in ISO-8601 UTC only
- ordering must use explicit indices (not timestamps)
- force `TZ=UTC` and `LC_ALL=C` where possible

### 5.4 Decision equivalence key
`(base_revision_digest, proposal_digest, policy_version, gate_results_normalized)`

If this key matches across replay, determinism is satisfied for v0.

## 6. Contracts
### 6.1 PatchProposal
Minimum fields:
- `proposal_id`
- `proposal_contract_version`
- `base_revision_digest`
- `patch` (unified diff or patch ops)
- `intent`
- `touched_paths`
- `rationale` (bounded)

Hard rules:
- patch must apply cleanly to base snapshot
- touched paths must match allowlist
- deny forbidden patterns (secrets, vendoring, large binaries)

### 6.2 RunRequest
- `repo_path`
- `task_spec`
- `checks`
- `seed`
- `max_attempts`
- `execution_envelope`
- optional `model_streams` (v0 default: 1)

### 6.3 Version and policy identity (required in artifacts)
- `run_contract_version`
- `decision_contract_version`
- `policy_version`
- `policy_digest`

## 7. Validation Pipeline (v0)
Stage 0 - Intake
- validate proposal schema
- deny malformed

Stage 1 - Patch Safety
- deny forbidden paths
- deny oversized patch
- deny secret patterns
- deny binary deltas unless explicitly allowlisted
- deny rename-heavy patches above cap unless refactor mode

Stage 2 - Apply + Snapshot
- apply patch to workspace clone
- record resulting tree digest

Stage 3 - Build Gate
- run deterministic build step
- deny on failure

Stage 4 - Test Gate
- run deterministic tests
- deny on failure
- capture failing tests + stack traces
- flake policy applies

Stage 5 - Static Gate (optional v0)
- lint/format as configured
- deny on failure

Acceptance:
- `accept = all_required_gates_pass AND no_policy_denies`

## 8. Flake Policy (v0)
`flake_policy.mode = deny | retry_then_deny | quarantine_allow`

Default: `retry_then_deny`
- retry failing gate up to N=2 with same inputs
- if outcomes disagree: `flake_detected=true` and deny

`quarantine_allow`:
- requires explicit `flake_quarantine.json`
- quarantined tests excluded from gating, but failures still recorded and surfaced loudly

## 9. Rejection Codes (stable enum v0)
- `SCHEMA_INVALID`
- `PATCH_APPLY_FAILED`
- `FORBIDDEN_PATH`
- `PATCH_TOO_LARGE`
- `SECRETS_DETECTED`
- `BINARY_DELTA_DENIED`
- `RENAME_CAP_EXCEEDED`
- `BUILD_FAILED`
- `TESTS_FAILED`
- `LINT_FAILED`
- `FLAKE_DETECTED`
- `NONDETERMINISTIC_ENV`
- `POLICY_DENY`

Decision artifacts include:
- `rejection_codes[]`
- `primary_rejection_code`

## 10. Artifacts and Ledger Layout
Workspace-relative:
`workspace/default/stabilizer/run/<run_id>/`

- `run.json` (inputs)
- `ledger.jsonl` (append-only)
- `attempts/<n>/`
  - `proposal.json`
  - `patch.diff`
  - `apply_result.json`
  - `checks/build.json`, `checks/build.log`
  - `checks/tests.json`, `checks/tests.log`
  - `checks/lint.json`, `checks/lint.log`
  - `metrics.json`
  - `decision.json`
  - `tree_digest.txt`

Promotion outputs:
- `promotion.json`
- `promotion_event` appended to `ledger.jsonl`

### 10.1 Tamper evidence
Each ledger entry includes:
- `entry_digest`
- `prev_entry_digest`

Run records `run_root_digest` as the terminal chain digest.

## 11. Promotion to Canonical (v0)
- Human-triggered only (`actor_type=human`)
- Records `actor_id` and `actor_source=ui|cli`
- Applies accepted patch to canonical branch head (fast-forward expected in v0)
- Creates Git commit with deterministic message template
- Records commit SHA and tree digest in `promotion.json`

## 12. Replay Contract (v0)
Replay is first-class and offline-capable.

Replay consumes:
- `run.json`
- `attempts/<n>/proposal.json`
- policy bundle (`policy_version`/`policy_digest`)
- recorded base revision

Replay produces:
- `replay_result.json`
- equivalence-key comparison result

Replay must not silently fetch external state to change decision outcome.

## 13. UI v0 - Lab Instrument Priority
### 13.1 Must-have first
Attempt Inspector is primary:
- left: proposal summary + gate results
- center: diff viewer + file tree
- right: failures with clickable stack traces

Actions:
- promote to canonical (accepted only)
- export patch
- copy failure report
- replay same inputs

### 13.2 Secondary
- runs list
- run detail timeline
- triage filters
- scoreboard charts

## 14. Minimal Threat Model (v0)
- Secrets in diff/logs: detect + deny; redact in UI copies.
- Prompt injection in rationale: rationale is untrusted text, never executable, never policy-authoritative.
- Path traversal in patch ops: deny `..`, absolute paths, drive escapes.
- Resource exhaustion: cap patch size, log size, runtime.
- Supply chain drift: enforce lockfile/container and record digests.

## 15. Metrics
- Time-to-green
- Attempts-to-green
- Rejection reason histogram
- Flake rate (target near 0)
- Drift rate (if requirements gate enabled)

## 16. ODR Requirement Admission (optional add-on)
Before stabilizer runs, requirements may be admitted through ODR to produce a canonical requirements contract artifact.

Minimal requirement contract v0:
- `contract_id`
- `contract_version`
- `goal`
- `acceptance_tests` (non-empty, verifiable)
- `out_of_scope`
- `constraints`
- `interfaces` (optional)
- `evaluation_plan`
- `risk_notes` (optional)

Guardrail:
- bounded refinement rounds (for example 3-5)
- deny non-converging specs unless explicitly force-accepted as `draft/unsafe`
