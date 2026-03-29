# ReviewRun CLI Guide

Last reviewed: 2026-03-28

## Purpose
Run manual snapshot-driven reviews without webhook automation.

## Commands
1. Review a PR:
   - `orket review pr --remote <gitea-url> --repo <owner/name> --pr <num>`
2. Review a diff:
   - `orket review diff --repo-root . --base <ref> --head <ref>`
3. Review selected files:
   - `orket review files --repo-root . --ref <ref> --paths a.py b.py`
4. Replay offline:
   - `orket review replay --run-dir workspace/default/review_runs/<run_id>/`
   - `--run-dir` replay consumes snapshot/policy through the shared validated review-bundle artifact loader, which also validates persisted review manifest, required manifest and lane-payload `run_id`, required lane-payload `control_plane_*` refs whenever the manifest declares them, orphaned lower-level manifest or lane `control_plane_*` refs, manifest or lane attempt/step refs that drift outside the declared `control_plane_run_id` lineage, lane-artifact execution-authority markers, and manifest-to-lane run/control-plane identifier alignment before replaying
   - direct `--snapshot snapshot.json --policy policy_resolved.json` replay also reuses that shared loader when those files are the canonical bundle artifacts from one review run directory, so the same persisted identifier checks apply there too

## Auth (PR command)
Precedence:
1. `--token`
2. `ORKET_GITEA_TOKEN`
3. `GITEA_TOKEN`

Token values are never persisted in ReviewRun artifacts.

PR remote truth rules:
1. `--remote` must be an `http` or `https` base URL.
2. `--remote` must match a configured git remote for `--repo-root` and the requested `--repo` before any authenticated request is sent.
3. An unbound remote fails the run before any outbound PR API request is made.

Files mode truth rule:
1. `orket review files` fails closed when any requested path is missing at the requested ref.

## Common Flags
1. `--policy <path>`: override default repo policy file.
2. `--max-files|--max-diff-bytes|--max-blob-bytes|--max-file-bytes`: snapshot bounds.
3. `--enable-model-assisted`: advisory model lane.
4. `--code-only`: force code-only input scope.
5. `--all-files`: force all-files input scope.
6. `--fail-on-blocked`: non-zero exit only when deterministic decision is `blocked`.
7. `--workspace <path>`: base workspace root.
8. `--json`: JSON output.
9. `--verbose`: include digest lines in human output.

Default scope is `code_only` unless policy or CLI override sets `all_files`.

## Output
Each run prints:
1. `run_id`
2. deterministic decision
3. artifact path
4. control-plane run/attempt state and start-step kind when durable control-plane publication is available
5. durable control-plane run/attempt/step refs when that publication exists

Default artifact root:
`workspace/default/review_runs/<run_id>/`

When JSON output includes a `control_plane` summary, it is a projection from durable control-plane records, declares `projection_source: control_plane_records` plus `projection_only: true`, fails closed if it carries projected run, attempt, or step ids while dropping projected run metadata, attempt state or ordinal, or step kind, fails closed if projected `attempt_state` or `attempt_ordinal` survives after projected `attempt_id` drops, fails closed if projected `step_kind` survives after projected `step_id` drops, fails closed if lower-level projected `attempt_id` or `step_id` survive after parent `run_id` or `attempt_id` drop, fails closed if projected `attempt_id` or `step_id` drift outside the projected `run_id` lineage, fails closed if its projected run or attempt or step refs drift from the enclosing review result and manifest control-plane refs, and also fails closed if the embedded manifest drops control-plane refs still carried by that returned summary. Fresh review manifest and lane-artifact serialization also fail closed if artifact `control_plane_run_id` drifts from artifact `run_id`, or if fresh attempt or step refs drift outside that declared control-plane run lineage. `review diff`, `review pr`, and `review files` surface that failure as the normal structured review error payload instead of an uncaught exception.
