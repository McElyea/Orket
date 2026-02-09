# Gitea Backup & Recovery Strategy (LOCAL ONLY)

## ⚠️ Security Notice

**DO NOT sync backups to cloud storage!**

Backups contain ALL private repositories. If synced to cloud and your account is compromised, all code is exposed. **Local-only backups** are the safest approach for private projects.

---

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

### Manual Backup

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

### Automated Backup (Windows Task Scheduler)

**Setup (Run PowerShell as Administrator)**:
```powershell
.\scripts\setup_windows_backup.ps1
```

This creates a scheduled task that:
- Runs daily at 3:00 AM
- Executes `backup_gitea.sh`
- Keeps last 7 backups
- Runs as your user account

**Manual commands**:
```powershell
# View task
Get-ScheduledTask -TaskName "Orket-Gitea-Daily-Backup"

# Run now
Start-ScheduledTask -TaskName "Orket-Gitea-Daily-Backup"

# Remove
Unregister-ScheduledTask -TaskName "Orket-Gitea-Daily-Backup"
```

---

## Backup Frequency Recommendations

| Scenario | Frequency | Retention |
|----------|-----------|-----------|
| **Active Development** | Daily | 7 days |
| **Production Use** | Daily | 14 days |
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

### ✅ Repos are Now Private by Default

**Already configured!** All new repos will be private.

**To verify**:
```bash
cd infrastructure/gitea/gitea/conf
grep "DEFAULT_PRIVATE" app.ini
# Should show: DEFAULT_PRIVATE = private
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

Via Web UI:
1. Go to repo → Settings
2. Check "Make Private"
3. Save

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

## Off-Site Backup (Optional - Advanced)

**If you need off-site backups** (for disaster recovery):

**Option 1: External Hard Drive**
```bash
# After backup, copy to external drive
cp backups/gitea/gitea_backup_*.tar.gz /mnt/external-drive/orket-backups/
```

**Option 2: Encrypted USB Drive**
```bash
# Encrypt backup before copying
gpg --symmetric --cipher-algo AES256 backups/gitea/gitea_backup_LATEST.tar.gz
# Copy .gpg file to USB drive
```

**Option 3: Network Attached Storage (NAS)**
```bash
# Mount NAS
net use Z: \\nas\backups /user:username password

# Copy backups
xcopy /Y backups\gitea\*.tar.gz Z:\orket\
```

**DO NOT** use cloud storage unless you:
1. Encrypt backups with strong password first
2. Understand the security implications
3. Have a specific compliance requirement

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

---

## Migration to New System

**Export from old system**:
```bash
./scripts/backup_gitea.sh
# Copy backups/gitea/gitea_backup_LATEST.tar.gz to USB/external drive
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
✅ **Private by default**: Configured automatically
✅ **Daily backups**: Keep last 7 days
✅ **Quick recovery**: ~5 minutes from backup
✅ **Never lose data**: Automated + verified backups
✅ **Secure**: No cloud exposure

**Setup checklist**:
- [x] Gitea configured for private repos
- [ ] Run: `.\scripts\setup_windows_backup.ps1` (as Administrator)
- [ ] Test backup: `.\scripts\backup_gitea.sh`
- [ ] Test restore: `.\scripts\restore_gitea.sh backups/gitea/gitea_backup_LATEST.tar.gz`
- [ ] Verify monthly
