# Orket First Run Setup Checklist

Use this checklist to configure a fresh local Orket environment.

## 1. Prerequisites
- Docker Desktop
- Git
- Python 3.10+

## 2. Clone
```bash
git clone https://github.com/McElyea/Orket.git
cd Orket
```

## 3. Environment File
```bash
cp .env.example .env
```

Fill required values in `.env`:
- `DASHBOARD_PASSWORD`
- `DASHBOARD_SECRET_KEY`
- `GITEA_ADMIN_USER`
- `GITEA_ADMIN_PASSWORD`
- `GITEA_ADMIN_EMAIL`
- `POSTGRES_PASSWORD`
- `MYSQL_PASSWORD`
- `MONGO_PASSWORD`

## 4. Python Dependencies
```bash
pip install -r requirements.txt
```

## 5. Start Gitea
```bash
cd infrastructure
docker-compose -f docker-compose.gitea.yml up -d
```

## 6. Complete Gitea Web Setup
Open `http://localhost:3000` and complete the installation form.

## 7. Configure Private Repositories
Set default repository visibility to private:
- Use `scripts/configure_gitea_privacy.sh`, or
- Configure in Gitea admin UI.

## 8. Configure Backups
Set backup path in `scripts/setup_windows_backup.ps1` and run:
```powershell
.\scripts\setup_windows_backup.ps1
```

## 9. Verify System
Run baseline verification:
```bash
python -m pytest tests/test_golden_flow.py -v
```

## 10. Security Checks
- `.env` is ignored by git
- `infrastructure/gitea/` is ignored by git
- backup directory is ignored by git
- backup target is on a different physical drive

## Related Docs
- `docs/ROADMAP.md`
- `docs/CREDENTIALS.md`
- `docs/SECURITY.md`
- `docs/RUNBOOK.md`
