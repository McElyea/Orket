# External Extension Template

Copy this template into a new repository and update:
1. `extension_id`
2. package name in `pyproject.toml`
3. workload ids and entrypoints
4. script defaults and ports

Validation commands:
1. `python -m orket_extension_sdk.validate . --json`
2. `python -m orket_extension_sdk.import_scan src --json`
3. `orket ext validate . --json`

Run local web app:
1. Start Orket host API (`python -m orket.interfaces.api` or your standard host launch path).
2. Set environment (optional):
   - `COMPANION_HOST_BASE_URL` (default `http://127.0.0.1:8000`)
   - `COMPANION_API_KEY` (required when host auth is enabled)
3. Launch template UI:
   - Unix: `./scripts/run.sh`
   - PowerShell: `./scripts/run.ps1`
4. Open `http://127.0.0.1:3000`.
