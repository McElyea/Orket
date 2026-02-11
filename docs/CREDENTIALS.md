# Credential Management Strategy

## Rule
All secrets belong in `.env`.

## Protected by `.gitignore`
- `.env`
- `user_settings.json`
- `*.db`
- `infrastructure/gitea/`
- `infrastructure/mysql/`

## Safe to Commit
- `config/organization.json`
- `config/*_example.json`
- `.env.example`

## Runtime Loading
- Python runtime uses `python-dotenv` to load `.env`.
- Docker services load `.env` with `env_file` or environment expansion.
- Generated sandboxes must read secrets from environment variables, not hardcoded values.

## Setup
1. Copy `.env.example` to `.env`.
2. Generate strong random secrets.
3. Replace template values before starting services.

## Rotation
1. Generate new value.
2. Update `.env`.
3. Restart dependent services.
4. Verify auth/session-dependent flows.

## Leak Response
1. Rotate leaked credentials immediately.
2. Remove exposed secrets from git history.
3. Force push cleaned history if required.
4. Notify collaborators to refresh local state.
