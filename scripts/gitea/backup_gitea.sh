#!/bin/bash
set -euo pipefail

# Backup Gitea data (repos, database, config).
# IMPORTANT: Backups should be on a different drive than source data.

BACKUP_DIR="${ORKET_BACKUP_DIR:-/mnt/v/OrketBackup}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME="gitea_backup_${TIMESTAMP}.tar.gz"

echo "Starting Gitea backup..."

mkdir -p "$BACKUP_DIR"

if tar -czf "$BACKUP_DIR/$BACKUP_NAME" \
    -C infrastructure \
    gitea/git/repositories \
    gitea/gitea/gitea.db \
    gitea/gitea/conf/app.ini \
    gitea/data \
    --exclude='gitea/log/*' \
    2>/dev/null; then
    SIZE=$(du -h "$BACKUP_DIR/$BACKUP_NAME" | cut -f1)
    echo "Backup complete: $BACKUP_NAME ($SIZE)"

    find "$BACKUP_DIR" -maxdepth 1 -type f -name "gitea_backup_*.tar.gz" | sort -r | tail -n +8 | xargs -r rm
    echo "Cleaned old backups (keeping last 7)"

    echo ""
    echo "Available backups:"
    ls -lh "$BACKUP_DIR"/gitea_backup_*.tar.gz | awk '{print "   " $9 " (" $5 ")"}'
else
    echo "Backup failed!"
    exit 1
fi
