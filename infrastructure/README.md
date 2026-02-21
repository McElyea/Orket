# Infrastructure

Infrastructure assets for local Gitea-backed development workflows.

## Gitea Service
Compose file: `infrastructure/docker-compose.gitea.yml`

### Commands
```bash
cd infrastructure
docker-compose -f docker-compose.gitea.yml up -d
docker-compose -f docker-compose.gitea.yml ps
docker-compose -f docker-compose.gitea.yml logs -f gitea
docker-compose -f docker-compose.gitea.yml down
```

Destructive cleanup:
```bash
docker-compose -f docker-compose.gitea.yml down -v
```

## Default Ports
1. `3000`: Gitea UI
2. `222`: Gitea SSH

## Related Docs
1. `docs/GITEA_WEBHOOK_SETUP.md`
2. `docs/GITEA_STATE_OPERATIONAL_GUIDE.md`
3. `docs/GITEA_BACKUP_STRATEGY.md`
