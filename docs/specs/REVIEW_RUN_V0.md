# ReviewRun v0 Contract

Last reviewed: 2026-03-27

## Summary
`ReviewRun` is a manual, snapshot-driven review primitive.

v0 requirements:
1. Input is a canonical `ReviewSnapshot`.
2. Policy is resolved locally and emits `policy_digest`.
3. Deterministic lane is required and authoritative.
4. Model-assisted lane is optional and advisory-only.
5. Artifacts are durable and replayable.

## Digest and Canonicalization
1. Algorithm: `sha256`.
2. Format: `sha256:<hex>`.
3. Canonical JSON rules:
   - UTF-8 bytes.
   - Keys sorted recursively.
   - Newlines normalized to `\n`.
   - Explicit optional/empty field handling in contract payloads.
   - Stable list ordering for contract lists (`changed_files` sorted by `path,status`).
   - Diff text is preserved except newline normalization.

## Input Contract
`ReviewSnapshot` includes:
1. `source`: `pr|diff|files`
2. `repo`: `remote`, `repo_id`, optional `server_id`
3. `base_ref`, `head_ref`
4. `bounds`: `max_files`, `max_diff_bytes`, `max_blob_bytes`, `max_file_bytes`
5. `truncation` (explicit)
6. `changed_files[]`
7. `diff_unified`
8. `context_blobs[]`
9. `metadata`
10. `snapshot_digest`

Input truth requirements:
1. `review pr` must bind the requested `--remote` base URL to a configured git remote for the local `repo_root` and target `owner/name` repo before any authenticated request is sent.
2. `review pr` only accepts `http` or `https` remote base URLs.
3. `review files` must fail closed when any requested path cannot be loaded from the requested ref; missing files are not represented as empty blobs.

## Policy Resolution
Precedence:
1. CLI overrides
2. repo policy `.orket/review_policy.json`
3. user settings `.orket/durable/config/user_settings.json` under `review_policy`
4. defaults (`review_policy_v0`)

`policy_digest` is computed from the resolved canonical policy payload.

### Input Scope Policy (Locked)
`input_scope.mode` controls what files are included in snapshots:
1. `code_only` (default): include only files with configured code extensions.
2. `all_files`: include all changed files.

Default behavior for v0 is `code_only` to avoid non-code drift in review inputs.

## Lanes
Deterministic lane:
1. Path policy checks
2. Forbidden pattern checks
3. Threshold checks
4. Deterministic test/lane hints
5. Stable finding ordering

Model-assisted lane:
1. Disabled by default
2. Bounded snapshot input only
3. Strict output contract validation
4. Advisory-only
5. Cannot override deterministic decision/exit semantics

## Replay Contract
`orket review replay`:
1. Never re-fetches PR/diff/files state.
2. Replay execution consumes only `snapshot.json` and `policy_resolved.json`.
3. When `--run-dir` is used, or when direct `--snapshot` and `--policy` inputs point at canonical bundle files from the same review run directory, the CLI must consume `snapshot.json` and `policy_resolved.json` through the shared validated review-bundle artifact loader, and that same loader must also validate persisted `run_manifest.json`, `deterministic_decision.json`, and optional `model_assisted_critique.json` execution-authority markers before replay.
4. Missing or malformed persisted review bundle artifacts or authority markers fail closed before replay.
5. Produces a new `run_id` and new artifact directory.

## Artifact Bundle
Base path:
`workspace/default/review_runs/<run_id>/`

Files:
1. `snapshot.json`
2. `policy_resolved.json`
3. `deterministic_decision.json`
4. `model_assisted_critique.json` (optional)
5. `run_manifest.json`
6. `replay_instructions.txt` (optional)

`run_manifest.json` minimum:
1. `run_id`
2. `snapshot_digest`
3. `policy_digest`
4. `review_run_contract_version: review_run_v0`
5. `deterministic_lane_version: deterministic_v0`
6. `model_lane_contract_version: review_critique_v0` (if enabled)
7. bounds and truncation summary
8. `auth_source: token_flag|token_env|none`
9. `execution_state_authority: control_plane_records`
10. `lane_outputs_execution_state_authoritative: false`

`run_manifest.json` optional control-plane refs:
1. `control_plane_run_id`
2. `control_plane_attempt_id`
3. `control_plane_step_id`

When durable control-plane publication is enabled for manual review runs, those refs must name the first-class `RunRecord`, initial `AttemptRecord`, and start `StepRecord` published for that review invocation.

Review-lane artifact authority markers:
1. `deterministic_decision.json` and `model_assisted_critique.json` must include `execution_state_authority: control_plane_records`.
2. Those same lane payloads must include `lane_output_execution_state_authoritative: false`.
3. When durable control-plane publication is enabled for the review run, those same lane payloads must also carry `control_plane_run_id`, `control_plane_attempt_id`, and `control_plane_step_id`.
4. `run_manifest.json` must include `execution_state_authority: control_plane_records` and `lane_outputs_execution_state_authoritative: false`.
5. These review artifact surfaces must fail closed if those execution-authority markers drift.
6. Those markers do not change deterministic review-decision authority; they only make execution-state authority explicit and non-local.
7. Review evidence consumers that score, inspect, compare, or replay persisted review bundles must use the shared validated review-bundle loader or artifact loader before treating lane JSON, snapshot, or resolved policy as trustworthy evidence.

Result projection requirement:
1. The returned review result and CLI JSON surface may include a `control_plane` summary projection.
2. When present, that projection must declare `projection_source: control_plane_records` and `projection_only: true`.
3. That projection is read from durable control-plane records and is not a second authority surface.
4. The embedded `manifest` returned through review result and CLI JSON must also fail closed if its persisted execution-authority markers drift.
5. Review-lane artifacts remain review evidence and decision input/output only; they are not execution-state authority.
