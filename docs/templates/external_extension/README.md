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

Companion UI stack (MVP locked):
1. React + Vite + TypeScript
2. SCSS Modules
3. Radix UI primitives
4. Lucide icons
5. Plain `fetch` through a thin typed API client

Build Companion frontend (optional when editing UI source):
1. `npm --prefix src/companion_app/frontend install`
2. `npm --prefix src/companion_app/frontend test`
3. `npm --prefix src/companion_app/frontend run build`

Run local web app:
1. Start Orket host API (`python -m orket.interfaces.api` or your standard host launch path).
2. Set environment:
   - `COMPANION_HOST_BASE_URL` (default `http://127.0.0.1:8000`)
   - `COMPANION_API_KEY` (required; gateway fails closed when missing)
   - `COMPANION_TIMEOUT_SECONDS` (default `45`)
   - `COMPANION_GATEWAY_REQUIRE_LOOPBACK` (default `true`)
   - `COMPANION_GATEWAY_REQUIRE_SAME_ORIGIN` (default `true` for mutating routes)
3. Launch template UI:
   - Unix: `./scripts/run.sh`
   - PowerShell: `./scripts/run.ps1`
4. Open `http://127.0.0.1:3000`.

Gateway hardening notes:
1. Mutating routes require same-origin requests by default and return `E_COMPANION_GATEWAY_CSRF_BLOCKED` when origin mismatches.
2. Requests from non-loopback clients are rejected by default with `E_COMPANION_GATEWAY_LOOPBACK_REQUIRED`.
3. Payload guardrails return `413` for oversized Companion config/chat/audio payloads.
4. Keep host/API auth strict by setting `ORKET_API_KEY`, `ORKET_COMPANION_API_KEY`, and optionally `ORKET_COMPANION_KEY_STRICT=true`.
