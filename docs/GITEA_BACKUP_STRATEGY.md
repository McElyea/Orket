# Gitea Backup & Recovery Strategy

## Storage Architecture

### Local Storage
All Gitea data is stored locally in: `infrastructure/gitea/`

**Critical data**:
- `gitea/git/repositories/` - All Git repos (your generated projects)
- `gitea/gitea/gitea.db` - SQLite database (users, PRs, issues, settings)
- `gitea/gitea/conf/app.ini` - Configuration
- `gitea/data/attachments/` - PR attachments, issue images
- `gitea/data/lfs/` - Large File Storage

**Ignored** (regenerated):
- `gitea/log/` - Application logs

---

## Backup Strategy

### Option 1: Manual Backup (Simple)

```bash
# Run backup script
./scripts/backup_gitea.sh

# Output: backups/gitea/gitea_backup_YYYYMMDD_HHMMSS.tar.gz
```

**What's backed up**:
- All repositories
- Database (users, PRs, issues)
- Configuration
- Attachments

**Retention**: Last 7 backups (auto-cleaned)

### Option 2: Scheduled Backup (Recommended)

**Windows Task Scheduler**:
```powershell
# Create daily backup task
$action = New-ScheduledTaskAction -Execute "bash" -Argument "c:\Source\Orket\scripts\backup_gitea.sh"
$trigger = New-ScheduledTaskTrigger -Daily -At 3am
Register-ScheduledTask -Action $action -Trigger $trigger -TaskName "Orket Gitea Backup"
```

**Linux/Mac cron**:
```bash
# Add to crontab (daily at 3am)
0 3 * * * cd /path/to/Orket && ./scripts/backup_gitea.sh
```

### Option 3: Cloud Sync (Best)

**Sync backups to cloud storage**:
```bash
# After backup, sync to cloud
./scripts/backup_gitea.sh
rclone copy backups/gitea/ remote:orket-backups/gitea/
```

**Supported cloud providers** (via rclone):
- Google Drive
- OneDrive
- Dropbox
- AWS S3
- Backblaze B2

---

## Backup Frequency Recommendations

| Scenario | Frequency | Retention |
|----------|-----------|-----------|
| **Active Development** | Daily | 7 days |
| **Production Use** | Hourly | 24 hours + weekly archives |
| **Stable/Archive** | Weekly | 4 weeks |

**Current recommendation**: **Daily at 3am** (low usage time)

---

## Recovery Procedures

### Full Restore

```bash
# Stop Gitea
cd infrastructure
docker-compose -f docker-compose.gitea.yml down

# Restore from backup
cd ..
./scripts/restore_gitea.sh backups/gitea/gitea_backup_YYYYMMDD_HHMMSS.tar.gz

# Gitea will restart automatically
```

### Selective Restore (Single Repo)

```bash
# Extract specific repo from backup
tar -xzf backups/gitea/gitea_backup_YYYYMMDD.tar.gz \
    gitea/git/repositories/orket/my-project.git \
    -O > /tmp/my-project.git.tar

# Restore to running Gitea
cd infrastructure/gitea/git/repositories/orket/
tar -xf /tmp/my-project.git.tar
```

---

## Privacy Settings

### Make Repos Private by Default

**Method 1: Web UI**
1. Go to http://localhost:3000
2. Click your profile → **Site Administration**
3. **Configuration** → **Repository**
4. Set **Default Private** = `true`
5. Save

**Method 2: Script** (recommended)
```bash
./scripts/configure_gitea_privacy.sh
cd infrastructure
docker-compose -f docker-compose.gitea.yml restart
```

**Method 3: Manual config edit**
```bash
# Edit infrastructure/gitea/gitea/conf/app.ini
[repository]
DEFAULT_PRIVATE = private
```

### Change Existing Repos to Private

Via Gitea API:
```bash
curl -X PATCH \
  "http://localhost:3000/api/v1/repos/Orket/test-project" \
  -u "Orket:your-password" \
  -H "Content-Type: application/json" \
  -d '{"private": true}'
```

---

## Disaster Recovery

### Scenario 1: Accidental Data Loss

**Recovery**: Restore from last backup (see Full Restore above)

**Time**: ~5 minutes

### Scenario 2: Corrupted Database

**Recovery**:
```bash
# Stop Gitea
docker-compose -f infrastructure/docker-compose.gitea.yml down

# Restore only database from backup
tar -xzf backups/gitea/gitea_backup_LATEST.tar.gz \
    gitea/gitea/gitea.db \
    -C infrastructure/

# Restart
docker-compose -f infrastructure/docker-compose.gitea.yml up -d
```

### Scenario 3: Complete System Failure

**Recovery** (on new machine):
1. Install Docker
2. Clone Orket repo
3. Restore backup: `./scripts/restore_gitea.sh backups/gitea/gitea_backup_LATEST.tar.gz`
4. Start Gitea: `cd infrastructure && docker-compose -f docker-compose.gitea.yml up -d`

**Time**: ~15 minutes

---

## Backup Verification

**Test backups monthly**:
```bash
# 1. Create test backup
./scripts/backup_gitea.sh

# 2. Stop production Gitea
cd infrastructure
docker-compose -f docker-compose.gitea.yml down

# 3. Restore and verify
cd ..
./scripts/restore_gitea.sh backups/gitea/gitea_backup_LATEST.tar.gz

# 4. Check repos and data
curl http://localhost:3000/api/v1/user/repos -u "Orket:password"
```

---

## Cloud Backup Setup (Recommended)

### Using rclone (supports all major clouds)

**Install rclone**:
```bash
# Windows
choco install rclone

# Linux/Mac
curl https://rclone.org/install.sh | sudo bash
```

**Configure remote**:
```bash
rclone config
# Follow prompts to add Google Drive, OneDrive, etc.
```

**Add to backup script**:
```bash
# At end of scripts/backup_gitea.sh
rclone copy "$BACKUP_DIR/$BACKUP_NAME" remote:orket-backups/gitea/
echo "☁️  Synced to cloud: remote:orket-backups/gitea/$BACKUP_NAME"
```

---

## Monitoring & Alerts

### Check Backup Health

```bash
# List recent backups
ls -lth backups/gitea/ | head -5

# Verify latest backup is recent
LATEST=$(ls -t backups/gitea/gitea_backup_*.tar.gz | head -1)
AGE=$(($(date +%s) - $(stat -c %Y "$LATEST")))
if [ $AGE -gt 86400 ]; then
    echo "⚠️  Latest backup is older than 24 hours!"
fi
```

### Email Alerts (optional)

Add to `scripts/backup_gitea.sh`:
```bash
# Send email if backup fails
if [ $? -ne 0 ]; then
    echo "Gitea backup failed!" | mail -s "Backup Alert" you@email.com
fi
```

---

## Migration to New System

**Export from old system**:
```bash
./scripts/backup_gitea.sh
# Copy backups/gitea/gitea_backup_LATEST.tar.gz to new system
```

**Import on new system**:
```bash
# On new machine
git clone https://github.com/McElyea/Orket.git
cd Orket
./scripts/restore_gitea.sh /path/to/gitea_backup_LATEST.tar.gz
```

---

## Summary

✅ **Local storage**: `infrastructure/gitea/` (bind mount, easy to backup)
✅ **Private by default**: Run `./scripts/configure_gitea_privacy.sh`
✅ **Daily backups**: Keep last 7 days
✅ **Cloud sync**: Use rclone for offsite backups
✅ **Quick recovery**: ~5 minutes from backup
✅ **Never lose data**: Automated + verified backups

**Recommended setup**:
1. Configure private repos by default
2. Set up daily automated backups (3am)
3. Sync to cloud storage (Google Drive, OneDrive)
4. Test restore monthly
