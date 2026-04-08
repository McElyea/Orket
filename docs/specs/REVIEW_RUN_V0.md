# ReviewRun v0 Contract

Last reviewed: 2026-03-28

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

Default forbidden-pattern severities:
1. `TODO|FIXME` defaults to `info` because the regex is intentionally broad and may match comments, docs, or strings.
2. `password\s*=` defaults to `high`.
3. Operators may override the resolved `forbidden_patterns` entries and raise `TODO|FIXME` severity if they want it to block PRs.

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
3. When `--run-dir` is used, or when direct `--snapshot` and `--policy` inputs point at canonical bundle files from the same review run directory, the CLI must consume `snapshot.json` and `policy_resolved.json` through the shared validated review-bundle artifact loader, and that same loader must also validate persisted `run_manifest.json`, `deterministic_decision.json`, and optional `model_assisted_critique.json` execution-authority markers plus required lane-payload `run_id` presence, required lane-payload `control_plane_*` refs whenever the manifest declares them, lower-level manifest or lane `control_plane_*` refs that survive without their parent run or attempt refs, attempt or step refs that drift outside the declared `control_plane_run_id` lineage, and manifest-to-lane run/control-plane identifier alignment before replay.
4. Missing or malformed persisted review bundle artifacts, authority markers, required lane-payload `run_id`, required lane-payload `control_plane_*` refs when the manifest declares them, lower-level manifest or lane `control_plane_*` refs that survive without parent run or attempt refs, attempt or step refs that drift outside the declared `control_plane_run_id` lineage, or manifest-to-lane identifiers fail closed before replay.
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
3. Those same lane payloads must also carry non-empty `run_id` matching `run_manifest.json`.
4. When durable control-plane publication is enabled for the review run, those same lane payloads must also carry `control_plane_run_id`, `control_plane_attempt_id`, and `control_plane_step_id`.
5. Those same lane payloads must also preserve control-plane id hierarchy: if `control_plane_attempt_id` or `control_plane_step_id` is present, `control_plane_run_id` must also be present, and if `control_plane_step_id` is present, `control_plane_attempt_id` must also be present.
6. `run_manifest.json` must include non-empty `run_id`, `execution_state_authority: control_plane_records`, and `lane_outputs_execution_state_authoritative: false`.
7. `run_manifest.json` must also preserve that same control-plane id hierarchy when it carries `control_plane_run_id`, `control_plane_attempt_id`, or `control_plane_step_id`.
8. These review artifact surfaces must fail closed if those execution-authority markers drift, if manifest or lane-payload `run_id` is missing, if fresh manifest or lane-payload `control_plane_run_id` drifts from the artifact `run_id`, if lower-level control-plane refs survive after parent run or attempt refs are dropped, or if fresh attempt or step refs drift outside the declared `control_plane_run_id` lineage.
9. Those markers do not change deterministic review-decision authority; they only make execution-state authority explicit and non-local.
10. Shared validated review-bundle loaders must also fail closed when persisted manifest or lane payload `run_id` is missing, when the manifest declares `control_plane_run_id` / `control_plane_attempt_id` / `control_plane_step_id` but a lane payload omits them, when lower-level manifest or lane `control_plane_attempt_id` / `control_plane_step_id` refs survive after parent run or attempt refs are dropped, when manifest or lane attempt or step refs drift outside the declared `control_plane_run_id` lineage, or when persisted manifest or lane payload `run_id`, `control_plane_run_id`, `control_plane_attempt_id`, or `control_plane_step_id` drift across the bundle.
11. Review evidence consumers that score, inspect, compare, or replay persisted review bundles must use the shared validated review-bundle loader or artifact loader before treating lane JSON, snapshot, or resolved policy as trustworthy evidence.

Result projection requirement:
1. The returned review result and CLI JSON surface may include a `control_plane` summary projection.
2. When present, that projection must declare `projection_source: control_plane_records` and `projection_only: true`.
3. When present, that projection must preserve projected lifecycle state: if `run_id` is present, it must also carry `run_state`, `workload_id`, `workload_version`, `policy_snapshot_id`, and `configuration_snapshot_id`; if `attempt_id` is present, it must also carry `attempt_state` and a positive `attempt_ordinal`; if `step_id` is present, it must also carry `step_kind`.
4. When present, that projection must also preserve control-plane id hierarchy: if `attempt_id` or `step_id` is present, `run_id` must also be present, if `step_id` is present, `attempt_id` must also be present, if `attempt_state` or `attempt_ordinal` is present, `attempt_id` must also be present, and if `step_kind` is present, `step_id` must also be present.
5. When present, that projection's `run_id` must match the enclosing review result `run_id`, its `attempt_id` and `step_id` must stay in that projected run lineage, its `attempt_id` and `step_id` must match the embedded manifest control-plane refs when those refs are present, and the embedded manifest must preserve matching `control_plane_run_id` / `control_plane_attempt_id` / `control_plane_step_id` refs whenever the returned projection carries them.
6. That projection is read from durable control-plane records and is not a second authority surface.
7. The embedded `manifest` returned through review result and CLI JSON must also fail closed if its persisted execution-authority markers or control-plane run identity drift, if its attempt or step refs drift outside the declared `control_plane_run_id` lineage, or if it omits control-plane refs still carried by the returned `control_plane` projection.
8. Review CLI commands must surface that serialization failure as a normal structured review error instead of an uncaught exception.
9. Review-lane artifacts remain review evidence and decision input/output only; they are not execution-state authority.
