# Orket First Run Setup Checklist

**Purpose**: Track all manual configuration steps needed when setting up Orket for the first time.

**Goal**: Eventually automate these in an interactive setup wizard (`orket init`)

---

## ✅ Prerequisites

### 1. Software Installation
- [ ] **Docker Desktop** (v4.60.0+) - [Download](https://www.docker.com/products/docker-desktop/)
- [ ] **Git** - [Download](https://git-scm.com/downloads)
- [ ] **Python 3.10+** - [Download](https://www.python.org/downloads/)
- [ ] **Git Bash** or **WSL** (for running .sh scripts on Windows)

### 2. Clone Repository
```bash
git clone https://github.com/McElyea/Orket.git
cd Orket
```

---

## 🔧 Configuration Steps

### Step 1: Create `.env` File
**File**: `.env` (root directory)

**Action**: Copy template and fill in values
```bash
cp .env.example .env
```

**Required values**:
```bash
# Dashboard
DASHBOARD_PASSWORD=<choose-strong-password>
DASHBOARD_SECRET_KEY=<generate-with: openssl rand -hex 32>

# Gitea Admin (will be created during Gitea setup)
GITEA_ADMIN_USER=<your-username>
GITEA_ADMIN_PASSWORD=<choose-strong-password>
GITEA_ADMIN_EMAIL=<your-email>

# Sandbox Databases (used in generated projects)
POSTGRES_PASSWORD=<choose-password>
MYSQL_PASSWORD=<choose-password>
MONGO_PASSWORD=<choose-password>
```

**Location**: Root directory (`c:\Source\Orket\.env`)

**Automation potential**: ✅ Can prompt user for values in setup wizard

---

### Step 2: Configure Backup Drive
**File**: `scripts/setup_windows_backup.ps1`

**Action**: Set backup location to **different drive** than source

**Line to change**:
```powershell
$BackupDrive = "V:\OrketBackup"  # Change to your backup drive
```

**User-specific values**:
- Backup drive letter (V:, D:, E:, etc.)
- Backup directory name

**Why**: Backups on same drive are useless if drive fails

**Automation potential**: ✅ Can prompt: "Which drive for backups? (V:, D:, E:)"

---

### Step 3: Install Dependencies
**Action**: Install Python packages
```bash
pip install -r requirements.txt
```

**Automation potential**: ✅ Can run automatically in setup wizard

---

### Step 4: Start Gitea
**Action**: Start Gitea Docker container
```bash
cd infrastructure
docker-compose -f docker-compose.gitea.yml up -d
```

**Automation potential**: ✅ Can run automatically

---

### Step 5: Complete Gitea Installation
**Action**: Web-based installation wizard

1. Open browser: http://localhost:3000
2. Complete installation form:
   - **Database**: SQLite3 (default)
   - **Site Title**: "Vibe Rail Gitea" (or your org name)
   - **Server Domain**: localhost
   - **Gitea Base URL**: http://localhost:3000/
   - **Administrator Account**:
     - Username: (from .env: GITEA_ADMIN_USER)
     - Password: (from .env: GITEA_ADMIN_PASSWORD)
     - Email: (from .env: GITEA_ADMIN_EMAIL)
3. Click "Install Gitea"

**Automation potential**: 🟡 Partial - can pre-configure some settings, but web wizard is interactive

---

### Step 6: Configure Gitea for Private Repos
**Action**: Set default repo visibility to private

**Method 1**: Already automated by setup scripts
```bash
./scripts/configure_gitea_privacy.sh
```

**Method 2**: Manual via Web UI
1. Go to http://localhost:3000
2. Profile → Site Administration → Configuration → Repository
3. Set **Default Private** = true

**Current status**: ✅ Already done (in session on 2026-02-09)

**Automation potential**: ✅ Already automated

---

### Step 7: Set Up Automated Backups
**Action**: Configure Windows Task Scheduler for daily backups

**Prerequisites**:
- Backup drive must exist and be accessible
- Run PowerShell as Administrator

**Command**:
```powershell
.\scripts\setup_windows_backup.ps1
```

**What it does**:
- Creates scheduled task "Orket-Gitea-Daily-Backup"
- Runs daily at 3:00 AM
- Saves to backup drive (V:\OrketBackup)
- Keeps last 7 backups

**User-specific values**:
- Backup time (default: 3:00 AM)
- Retention (default: 7 days)

**Automation potential**: ✅ Already automated (just need to run once)

---

### Step 8: Configure Organization Settings
**File**: `config/organization.json`

**Action**: Customize for your organization (optional)

**Values to customize**:
```json
{
  "name": "Vibe Rail",  // Your org name
  "vision": "...",       // Your vision
  "ethos": "...",        // Your ethos
  "branding": {
    "colorscheme": {
      "primary": "#1A202C",   // Your colors
      "secondary": "#2D3748",
      "accent": "#4A5568"
    }
  },
  "architecture": {
    "idesign_threshold": 7  // Complexity gate (default: 7)
  }
}
```

**Automation potential**: 🟡 Can prompt for org name, use defaults for rest

---

### Step 9: Test Backup & Restore
**Action**: Verify backup system works

```bash
# Test backup
./scripts/backup_gitea.sh
# Should create: V:\OrketBackup\gitea_backup_YYYYMMDD_HHMMSS.tar.gz

# Test restore (in safe environment)
./scripts/restore_gitea.sh V:\OrketBackup\gitea_backup_YYYYMMDD_HHMMSS.tar.gz
```

**Automation potential**: ✅ Can run test backup in setup wizard

---

### Step 10: Verify Everything Works
**Action**: Run sanity test

```bash
python -m pytest tests/test_golden_flow.py -v
```

**Expected**: 2/2 tests passing

**Automation potential**: ✅ Can run automatically and show results

---

## 📋 User-Specific Settings Summary

These values must be configured per user/environment:

| Setting | File | Line/Key | Example | Prompt |
|---------|------|----------|---------|--------|
| **Dashboard Password** | `.env` | `DASHBOARD_PASSWORD` | `strong-password-123` | "Choose dashboard password:" |
| **Gitea Admin User** | `.env` | `GITEA_ADMIN_USER` | `admin` | "Gitea admin username:" |
| **Gitea Admin Password** | `.env` | `GITEA_ADMIN_PASSWORD` | `secure-pass-456` | "Gitea admin password:" |
| **Gitea Admin Email** | `.env` | `GITEA_ADMIN_EMAIL` | `you@email.com` | "Gitea admin email:" |
| **Backup Drive** | `setup_windows_backup.ps1` | `$BackupDrive` | `V:\OrketBackup` | "Backup drive (V:, D:, E:):" |
| **Backup Time** | `setup_windows_backup.ps1` | `$BackupTime` | `03:00` | "Backup time (HH:MM):" |
| **Org Name** | `config/organization.json` | `name` | `Vibe Rail` | "Organization name:" |
| **iDesign Threshold** | `config/organization.json` | `architecture.idesign_threshold` | `7` | "Complexity threshold (5-10):" |

---

## 🤖 Future: Interactive Setup Wizard

**Command**: `orket init` (not yet implemented)

**Flow**:
```
Welcome to Orket Setup! 🚀

This wizard will configure Orket for your environment.

Step 1/8: Dashboard Credentials
  Dashboard password: ************
  Secret key: [auto-generated]

Step 2/8: Gitea Admin
  Admin username: admin
  Admin password: ************
  Admin email: you@email.com

Step 3/8: Backup Configuration
  Backup drive (V:, D:, E:): V:
  Backup time (HH:MM): 03:00
  Retention (days): 7

Step 4/8: Organization Settings
  Organization name: Vibe Rail
  Complexity threshold (5-10): 7

Step 5/8: Installing Dependencies...
  ✅ pip install -r requirements.txt

Step 6/8: Starting Gitea...
  ✅ docker-compose -f infrastructure/docker-compose.gitea.yml up -d

Step 7/8: Configuring Gitea...
  ✅ Private repos by default
  ✅ Admin user created

Step 8/8: Setting up backups...
  ✅ Scheduled task created
  ✅ Test backup successful

✅ Setup Complete!

Next steps:
  1. Visit http://localhost:3000 (Gitea)
  2. Run: python orket/orket.py test-epic
  3. Read: docs/GETTING_STARTED.md
```

**Implementation**: See ROADMAP.md Phase 5.2 (User Onboarding)

---

## 🔒 Security Checklist

After setup, verify:

- [ ] `.env` is in .gitignore (never committed)
- [ ] `infrastructure/gitea/` is in .gitignore
- [ ] `backups/` is in .gitignore
- [ ] Backup drive is on different physical disk
- [ ] Gitea repos are private by default
- [ ] Strong passwords used (>12 characters, mixed case, numbers, symbols)

---

## 🐛 Troubleshooting Common Setup Issues

### Issue: Gitea won't start
**Symptom**: `docker-compose up` fails
**Solution**:
1. Check Docker Desktop is running
2. Check port 3000 is not already in use: `netstat -ano | findstr :3000`
3. Check logs: `docker-compose -f infrastructure/docker-compose.gitea.yml logs`

### Issue: Backup script fails
**Symptom**: "Permission denied" or "No such file or directory"
**Solution**:
1. Verify backup drive exists: `Test-Path V:\OrketBackup`
2. Create directory manually: `New-Item -ItemType Directory -Path V:\OrketBackup`
3. Check Git Bash is installed: `bash --version`

### Issue: Scheduled task doesn't run
**Symptom**: No backups appearing in V:\OrketBackup
**Solution**:
1. Check task exists: `Get-ScheduledTask -TaskName "Orket-Gitea-Daily-Backup"`
2. Check task history: Task Scheduler → Orket-Gitea-Daily-Backup → History
3. Run manually to test: `Start-ScheduledTask -TaskName "Orket-Gitea-Daily-Backup"`

### Issue: Tests fail
**Symptom**: `pytest tests/test_golden_flow.py` fails
**Solution**:
1. Verify dependencies installed: `pip list | grep orket`
2. Check Python version: `python --version` (need 3.10+)
3. Run verbose: `pytest tests/test_golden_flow.py -v -s`

---

## 📚 Related Documentation

- [ROADMAP.md](ROADMAP.md) - Development roadmap
- [GITEA_BACKUP_STRATEGY.md](GITEA_BACKUP_STRATEGY.md) - Backup details
- [CREDENTIALS.md](CREDENTIALS.md) - Credential management
- [PROJECT.md](PROJECT.md) - Project overview

---

## ✅ Setup Completion Checklist

Before starting development, verify:

- [ ] `.env` file created with all required values
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] Gitea running (http://localhost:3000 accessible)
- [ ] Gitea admin account created
- [ ] Gitea configured for private repos
- [ ] Backup drive configured (different from source)
- [ ] Automated backups scheduled (Windows Task Scheduler)
- [ ] Test backup successful (check V:\OrketBackup)
- [ ] Sanity test passing (`pytest tests/test_golden_flow.py`)
- [ ] Organization settings customized (optional)

**When all checked**: ✅ Ready to start using Orket!

---

## 🎯 Post-Setup: First Project

Try running a test epic:
```bash
python orket/orket.py core_baseline
```

Or explore the board:
```bash
python orket/cli.py board
```
