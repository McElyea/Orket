# ReviewRun CLI Guide

Last reviewed: 2026-03-27

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
   - `--run-dir` replay consumes snapshot/policy through the shared validated review-bundle artifact loader, which also validates persisted review manifest and lane-artifact execution-authority markers before replaying
   - direct `--snapshot snapshot.json --policy policy_resolved.json` replay also reuses that shared loader when those files are the canonical bundle artifacts from one review run directory

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

When JSON output includes a `control_plane` summary, it is a projection from durable control-plane records and declares `projection_source: control_plane_records` plus `projection_only: true`.
