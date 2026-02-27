# Gitea Backup and Recovery Strategy

Last reviewed: 2026-02-27

## Scope
Local-only backup/restore guidance for Gitea data used by Orket.

## Data Locations
Primary local data root:
1. `infrastructure/gitea/`

Critical paths:
1. `infrastructure/gitea/git/repositories/`
2. `infrastructure/gitea/gitea/gitea.db`
3. `infrastructure/gitea/gitea/conf/app.ini`
4. `infrastructure/gitea/data/attachments/`
5. `infrastructure/gitea/data/lfs/`

## Backup Command
```bash
./scripts/backup_gitea.sh
```

Output archive pattern:
1. `backups/gitea/gitea_backup_YYYYMMDD_HHMMSS.tar.gz`

Retention:
1. Keep latest 7 backups by default.

## Restore Command
```bash
./scripts/restore_gitea.sh backups/gitea/gitea_backup_YYYYMMDD_HHMMSS.tar.gz
```

Typical restore flow:
1. Stop Gitea stack.
2. Run restore script with selected archive.
3. Start Gitea and validate repo/DB integrity.

## Windows Scheduled Backup
Setup helper script:
```powershell
.\scripts\setup_windows_backup.ps1
```

This configures a scheduled daily backup task on local machine.

## Validation Checklist
After backup:
1. Archive exists and size is non-trivial.
2. Backup timestamp is recent.

After restore:
1. Gitea UI loads.
2. Expected repositories are present.
3. DB-backed metadata (issues/PRs/users) is accessible.

## Security Notes
1. Backups contain private repositories and metadata.
2. Prefer local storage; do not upload unencrypted archives to cloud storage.
3. If off-site copy is required, encrypt backup artifacts before transfer.

## Related Docs
1. `docs/GITEA_STATE_OPERATIONAL_GUIDE.md`
2. `docs/GITEA_WEBHOOK_SETUP.md`
3. `docs/PRODUCT_PUBLISHING.md`
