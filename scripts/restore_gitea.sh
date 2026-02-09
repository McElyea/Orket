#!/bin/bash
# Restore Gitea from backup

if [ -z "$1" ]; then
    echo "Usage: ./restore_gitea.sh <backup_file>"
    echo ""
    echo "Available backups:"
    ls -lh backups/gitea/gitea_backup_*.tar.gz 2>/dev/null | awk '{print "  " $9 " (" $5 ")"}'
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "❌ Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "⚠️  WARNING: This will overwrite current Gitea data!"
read -p "Continue? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "❌ Restore cancelled"
    exit 0
fi

# Stop Gitea
echo "🛑 Stopping Gitea..."
cd infrastructure
docker-compose -f docker-compose.gitea.yml down

# Backup current data (just in case)
SAFETY_BACKUP="backups/gitea/pre_restore_$(date +%Y%m%d_%H%M%S).tar.gz"
echo "💾 Creating safety backup: $SAFETY_BACKUP"
tar -czf "../$SAFETY_BACKUP" gitea/ 2>/dev/null

# Restore from backup
echo "📥 Restoring from: $BACKUP_FILE"
cd ..
tar -xzf "$BACKUP_FILE" -C infrastructure/

# Restart Gitea
echo "🚀 Starting Gitea..."
cd infrastructure
docker-compose -f docker-compose.gitea.yml up -d

echo "✅ Restore complete!"
echo "🔗 Gitea: http://localhost:3000"
