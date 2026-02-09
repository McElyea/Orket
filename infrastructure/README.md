# Vibe Rail Infrastructure

## Gitea (Git + CI/CD)

**Purpose**: Central Git repository host and CI/CD orchestration for Orket-generated projects.

### Quick Start

```bash
# Start Gitea
cd infrastructure
docker-compose -f docker-compose.gitea.yml up -d

# Check status
docker-compose -f docker-compose.gitea.yml ps

# View logs
docker-compose -f docker-compose.gitea.yml logs -f gitea

# Stop Gitea
docker-compose -f docker-compose.gitea.yml down

# Stop and delete all data (destructive!)
docker-compose -f docker-compose.gitea.yml down -v
```

### Initial Setup

1. **Start Gitea**: `docker-compose -f docker-compose.gitea.yml up -d`
2. **Open browser**: http://localhost:3000
3. **Complete installation wizard**:
   - Database: SQLite (pre-configured)
   - Domain: localhost
   - HTTP Port: 3000
   - Application URL: http://localhost:3000/
   - Admin account: Create your credentials
4. **Enable Gitea Actions**:
   - Already enabled via `GITEA__actions__ENABLED=true`

### Port Allocation

- **3000**: Gitea web UI
- **222**: Gitea SSH (for git clone via SSH)

### Architecture

```
Gitea (localhost:3000)
  ├── Repo: project-a
  ├── Repo: project-b
  └── Repo: project-c

Each repo can trigger Gitea Actions to:
  1. Build Docker images
  2. Deploy to sandbox (docker-compose up)
  3. Run tests (pytest, playwright)
  4. Report results back to Gitea
```

### Sandbox Projects

When Orket generates a project and it passes code review:
1. Create repo in Gitea: `orket/project-name`
2. Push code to Gitea
3. Gitea Actions triggers sandbox deployment
4. Sandbox runs at allocated ports (8001+, 3001+)
5. User tests in sandbox during UAT phase
6. When Rock → Done, sandbox cleanup triggered

### Notes

- **Data persistence**: Stored in Docker volume `gitea-data`
- **Docker socket**: Mounted to allow Gitea Actions to manage Docker containers
- **Network**: Uses `vibe-rail` bridge network for isolation
