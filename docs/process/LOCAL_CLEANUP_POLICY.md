# Local Space Conservation Policy

Automated cleanup is available for parity-verified published projects.

## Defaults
1. `45 days` unchanged -> move local folder to archive.
2. `90 days` in archive -> permanent delete.
3. Cleanup considers only registry entries with `parity_verified=true`.
4. Cleanup skips dirty git paths by default.

## Registry
Publisher writes metadata to:
`/.orket/project_publish_registry.json`

## Commands
Manual dry-run:
```bash
python scripts/cleanup_published_projects.py
```

Manual execute (default thresholds):
```bash
python scripts/cleanup_published_projects.py --execute
```

Custom thresholds:
```bash
python scripts/cleanup_published_projects.py --execute --archive-days 30 --hard-delete-days 75
```

## Scheduled Automation
Workflow: `.gitea/workflows/project_cleanup.yml`

Required variable:
1. `ENABLE_PROJECT_LOCAL_CLEANUP=true`

Optional variables:
1. `PROJECT_CLEANUP_SOURCE_DIR=product`
2. `PROJECT_CLEANUP_ARCHIVE_DAYS=45`
3. `PROJECT_CLEANUP_HARD_DELETE_DAYS=90`

## Safety
1. Scheduled cleanup is constrained by parity-verified registry entries.
2. It never acts on folders not recorded by publish automation.
