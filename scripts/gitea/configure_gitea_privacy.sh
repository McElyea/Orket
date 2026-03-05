#!/bin/bash
# Configure Gitea to create private repos by default

GITEA_CONFIG="infrastructure/gitea/gitea/conf/app.ini"

if [ ! -f "$GITEA_CONFIG" ]; then
    echo "❌ Gitea not yet initialized. Start Gitea first."
    exit 1
fi

# Backup original config
cp "$GITEA_CONFIG" "$GITEA_CONFIG.backup"

# Add or update DEFAULT_PRIVATE setting
if grep -q "DEFAULT_PRIVATE" "$GITEA_CONFIG"; then
    sed -i 's/DEFAULT_PRIVATE = .*/DEFAULT_PRIVATE = private/' "$GITEA_CONFIG"
    echo "✅ Updated DEFAULT_PRIVATE to private"
else
    # Add under [repository] section
    sed -i '/\[repository\]/a DEFAULT_PRIVATE = private' "$GITEA_CONFIG"
    echo "✅ Added DEFAULT_PRIVATE = private"
fi

echo "🔄 Restart Gitea for changes to take effect:"
echo "   cd infrastructure"
echo "   docker-compose -f docker-compose.gitea.yml restart"
