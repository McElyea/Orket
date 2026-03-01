# ReviewRun CLI Guide

Last reviewed: 2026-03-01

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

## Auth (PR command)
Precedence:
1. `--token`
2. `ORKET_GITEA_TOKEN`
3. `GITEA_TOKEN`

Token values are never persisted in ReviewRun artifacts.

## Common Flags
1. `--policy <path>`: override default repo policy file.
2. `--max-files|--max-diff-bytes|--max-blob-bytes|--max-file-bytes`: snapshot bounds.
3. `--enable-model-assisted`: advisory model lane.
4. `--fail-on-blocked`: non-zero exit only when deterministic decision is `blocked`.
5. `--workspace <path>`: base workspace root.
6. `--json`: JSON output.
7. `--verbose`: include digest lines in human output.

## Output
Each run prints:
1. `run_id`
2. deterministic decision
3. artifact path

Default artifact root:
`workspace/default/review_runs/<run_id>/`

