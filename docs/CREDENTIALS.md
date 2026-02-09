# Credential Management Strategy (v0.3.8)

## Philosophy: Single Source of Truth

**All secrets belong in `.env`** - nowhere else.

## Current Strategy ✅

### What's Protected
1. ✅ **`.env`** - In .gitignore, contains all secrets
2. ✅ **`user_settings.json`** - In .gitignore, contains user preferences
3. ✅ **`*.db`** - In .gitignore, contains local data
4. ✅ **`infrastructure/gitea/`** - In .gitignore, contains Gitea repos/config
5. ✅ **`infrastructure/mysql/`** - In .gitignore, contains MySQL data

### Files That Are Safe to Commit
- ❌ `config/organization.json` - **Public config** (no secrets)
- ❌ `config/bottleneck_thresholds_example.json` - **Example** (no secrets)
- ❌ `.env.example` - **Template** (no actual values)

## Credential Hierarchy

```
┌────────────────────────────────────────────────────────────┐
│ .env (SINGLE SOURCE OF TRUTH)                              │
│ ├── Dashboard credentials                                  │
│ ├── Gitea admin credentials                                │
│ ├── Sandbox database credentials                           │
│ ├── External API keys (OpenAI, Anthropic, etc.)           │
│ └── Orket internal secrets (encryption, sessions)         │
└────────────────────────────────────────────────────────────┘
          ↓                    ↓                    ↓
    ┌─────────┐          ┌─────────┐          ┌─────────┐
    │ Orket   │          │ Gitea   │          │Sandboxes│
    │ Runtime │          │ Docker  │          │ Docker  │
    └─────────┘          └─────────┘          └─────────┘
```

## Loading Credentials

### In Python (Orket Core)

```python
import os
from dotenv import load_dotenv

# Load at app startup
load_dotenv()

# Access credentials
dashboard_password = os.getenv("DASHBOARD_PASSWORD")
gitea_admin_user = os.getenv("GITEA_ADMIN_USER")
```

### In Docker Compose

```yaml
services:
  gitea:
    environment:
      - GITEA__security__SECRET_KEY=${GITEA_SECRET_KEY}
    env_file:
      - ../.env  # Load from root .env
```

### In Generated Projects (Sandboxes)

When Orket generates a project, inject credentials from `.env`:

```python
# In SandboxOrchestrator._generate_compose_file()
def _inject_credentials(self, compose_content: str) -> str:
    """Replace placeholders with actual credentials from .env."""
    load_dotenv()

    replacements = {
        "${POSTGRES_PASSWORD}": os.getenv("POSTGRES_PASSWORD", "postgres"),
        "${MYSQL_PASSWORD}": os.getenv("MYSQL_PASSWORD", "mysql"),
        "${MONGO_PASSWORD}": os.getenv("MONGO_PASSWORD", "mongo")
    }

    for placeholder, value in replacements.items():
        compose_content = compose_content.replace(placeholder, value)

    return compose_content
```

## Security Best Practices

### ✅ DO
1. **Store all secrets in `.env`** (dashboard, Gitea, databases, APIs)
2. **Use `.env.example`** as a template (committed to git)
3. **Generate strong passwords** (use `openssl rand -hex 32`)
4. **Rotate credentials regularly** (especially after team changes)
5. **Use different passwords** per service (avoid reuse)

### ❌ DON'T
1. ❌ **Never commit `.env`** to git
2. ❌ **Never hardcode credentials** in Python/JS files
3. ❌ **Never put secrets in `config/organization.json`**
4. ❌ **Never share credentials** via email/Slack
5. ❌ **Never use default passwords** in production

## Setup for New Users

### 1. Clone Repo
```bash
git clone https://github.com/McElyea/Orket.git
cd Orket
```

### 2. Create `.env` from Template
```bash
cp .env.example .env
```

### 3. Generate Secure Credentials
```bash
# Generate strong passwords
openssl rand -hex 32  # For SECRET_KEY
openssl rand -base64 24  # For DASHBOARD_PASSWORD
```

### 4. Fill in `.env`
Edit `.env` and replace all `change-me` values.

### 5. Verify Protection
```bash
# Should return empty (means .env is ignored)
git status .env
```

## Credential Rotation

When rotating credentials:

1. **Generate new value**:
   ```bash
   openssl rand -hex 32
   ```

2. **Update `.env`**:
   ```bash
   # Old
   DASHBOARD_SECRET_KEY=old-secret-change-me

   # New
   DASHBOARD_SECRET_KEY=a1b2c3d4e5f6...
   ```

3. **Restart services**:
   ```bash
   # Restart Orket
   python orket/orket.py

   # Restart Gitea
   cd infrastructure
   docker-compose -f docker-compose.gitea.yml restart
   ```

4. **Update dependent configs** (if any services cached old value)

## Audit Checklist

Run this periodically:

```bash
# 1. Verify .env is not tracked
git ls-files | grep .env
# Should be empty (except .env.example)

# 2. Search for hardcoded secrets
rg -i "password|secret|key" --type py --type js | grep -v ".env"
# Review results for hardcoded values

# 3. Check .gitignore coverage
cat .gitignore | grep -E "\.env|gitea|mysql"
# Should see all infrastructure directories
```

## Emergency: Leaked Credentials

If `.env` is accidentally committed:

1. **Immediately rotate ALL credentials** in `.env`
2. **Remove from git history**:
   ```bash
   git filter-branch --force --index-filter \
     "git rm --cached --ignore-unmatch .env" \
     --prune-empty --tag-name-filter cat -- --all
   ```
3. **Force push** (if already pushed to remote):
   ```bash
   git push origin --force --all
   ```
4. **Notify team** to pull latest and regenerate `.env`

---

## Summary: Is This the Best We Can Do?

**YES** - This is industry standard:

✅ Single source of truth (`.env`)
✅ Not committed to git (`.gitignore`)
✅ Template provided (`.env.example`)
✅ Loaded at runtime (python-dotenv, docker env_file)
✅ Hierarchical (Orket → Gitea → Sandboxes)

**Alternative approaches** (and why we don't use them):
- ❌ **HashiCorp Vault** - Overkill for local-first tool
- ❌ **AWS Secrets Manager** - Breaks "local-first" sovereignty
- ❌ **Encrypted config files** - Adds complexity, key management issues

**Our approach is optimal** for:
- Local-first philosophy ✅
- Single-user or small team ✅
- No external dependencies ✅
- Simple and auditable ✅
