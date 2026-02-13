# Product Repo Publishing (Gitea)

Use this when you want each `<source-dir>/*` project mirrored into Gitea as its own repository and pushed by automation.

## What It Does
1. Discovers folders under `<source-dir>/` (default `product/`).
2. Creates repos in Gitea (unless `--no-create`).
3. Uses `git subtree split` and pushes each project to its own repo branch.
4. Can verify parity (remote head SHA + tree manifest).
5. Can optionally delete local project folders after successful parity verification.

## Required Env Vars
```bash
GITEA_URL=http://localhost:3000
GITEA_ADMIN_USER=admin
GITEA_ADMIN_PASSWORD=your-password
GITEA_PRODUCT_OWNER=Orket
```

## Commands
Dry-run first:
```bash
python scripts/publish_products_to_gitea.py
```

Execute publish:
```bash
python scripts/publish_products_to_gitea.py --execute --verify-parity --private --force
```

Flexible source directory:
```bash
python scripts/publish_products_to_gitea.py --execute --verify-parity --source-dir bin/projects
```

Optional local deletion after verification:
```bash
python scripts/publish_products_to_gitea.py --execute --verify-parity --delete-local --source-dir product
```

Publish selected projects only:
```bash
python scripts/publish_products_to_gitea.py --execute --projects sneaky_price_watch price_arbitrage
```

## Notes
1. Destination repos are named after folder names by default (`--repo-prefix` to change).
2. Default branch target is current local branch; override with `--branch`.
3. `--delete-local` is optional and gated behind `--verify-parity`.
4. `--force` is useful on first sync if histories differ.
5. Source of truth remains the monorepo unless you choose otherwise.

## Push Automation
Workflow: `.gitea/workflows/product_publish.yml`

Behavior:
1. Triggers on push to `main` with changes in `product/**` or `bin/**`.
2. Runs only with repo variable `ENABLE_PRODUCT_REPO_PUBLISH=true`.
3. Uses `self-hosted` runner (local/private Gitea reachability).
4. Performs publish + parity verification only (no delete in CI).

Branch policy:
1. Feature branches open PRs and merge to `main`.
2. Publish automation executes on merge-to-main push.
3. Destination branch defaults to ref name unless overridden.

## Governance Ownership
1. Coder owns code changes.
2. Reviewer owns PR approval/merge.
3. Guard owns policy gates (vars, secrets, parity checks).
4. Workflow owns push automation execution.

## Required Repo Configuration (Gitea Actions)
Repository variable:
- `ENABLE_PRODUCT_REPO_PUBLISH=true`

Optional repository variables:
- `PRODUCT_PUBLISH_SOURCE_DIR=product`
- `PRODUCT_PUBLISH_TARGET_BRANCH=main`
- `PRODUCT_PUBLISH_REPO_PREFIX=`

Required repository secrets:
- `GITEA_URL`
- `GITEA_ADMIN_USER`
- `GITEA_ADMIN_PASSWORD`
- `GITEA_PRODUCT_OWNER`

## Safety Defaults
1. CI job does not pass `--delete-local`.
2. Local deletion remains explicit/manual and requires:
- `--verify-parity`
- `--delete-local`
