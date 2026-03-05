#!/bin/bash
# Backup Gitea data (repos, database, config)
# IMPORTANT: Backups should be on a DIFFERENT DRIVE than source data

# Backup location (change to your backup drive)
# Default: V:\OrketBackup (Windows) or /mnt/backup/orket (Linux)
BACKUP_DIR="${ORKET_BACKUP_DIR:-/mnt/v/OrketBackup}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME="gitea_backup_${TIMESTAMP}.tar.gz"

echo "📦 Starting Gitea backup..."

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Create timestamped backup
tar -czf "$BACKUP_DIR/$BACKUP_NAME" \
    -C infrastructure \
    gitea/git/repositories \
    gitea/gitea/gitea.db \
    gitea/gitea/conf/app.ini \
    gitea/data \
    --exclude='gitea/log/*' \
    2>/dev/null

if [ $? -eq 0 ]; then
    SIZE=$(du -h "$BACKUP_DIR/$BACKUP_NAME" | cut -f1)
    echo "✅ Backup complete: $BACKUP_NAME ($SIZE)"

    # Keep only last 7 backups
    cd "$BACKUP_DIR"
    ls -t gitea_backup_*.tar.gz | tail -n +8 | xargs -r rm
    echo "🗑️  Cleaned old backups (keeping last 7)"

    # List current backups
    echo ""
    echo "📋 Available backups:"
    ls -lh gitea_backup_*.tar.gz | awk '{print "   " $9 " (" $5 ")"}'
else
    echo "❌ Backup failed!"
    exit 1
fi
