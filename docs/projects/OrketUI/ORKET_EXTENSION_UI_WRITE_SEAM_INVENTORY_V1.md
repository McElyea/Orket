# ORKET_EXTENSION_UI_WRITE_SEAM_INVENTORY_V1

Last updated: 2026-04-09
Status: Active shipped provenance support doc
Authority status: Active Orket-side shipped provenance support doc. Records the current write-seam inventory for OrketUI and does not itself admit new host behavior.
Owner: Orket Core
Related docs: [docs/projects/archive/OrketUI/OUI04092026-LANE-CLOSEOUT/CLOSEOUT.md](docs/projects/archive/OrketUI/OUI04092026-LANE-CLOSEOUT/CLOSEOUT.md), [ORKET_EXTENSION_UI_REQUIREMENTS_V1.md](docs/projects/OrketUI/ORKET_EXTENSION_UI_REQUIREMENTS_V1.md), [ORKET_EXTENSION_UI_HOST_SEAM_MAP_V1.md](docs/projects/OrketUI/ORKET_EXTENSION_UI_HOST_SEAM_MAP_V1.md), [ORKET_EXTENSION_UI_OBJECT_MODEL_V1.md](docs/projects/OrketUI/ORKET_EXTENSION_UI_OBJECT_MODEL_V1.md), [docs/specs/CARD_AUTHORING_SURFACE_V1.md](docs/specs/CARD_AUTHORING_SURFACE_V1.md), [docs/specs/FLOW_AUTHORING_SURFACE_V1.md](docs/specs/FLOW_AUTHORING_SURFACE_V1.md), [docs/API_FRONTEND_CONTRACT.md](docs/API_FRONTEND_CONTRACT.md), [CURRENT_AUTHORITY.md](CURRENT_AUTHORITY.md)

## Purpose

Record the truthful shipped status of the OrketUI write seams.

This doc exists so the lane does not drift from a truthful read-backed slice into either false-green write claims or stale "planned-only" language after the host surfaces ship.

## Current inventory result

All currently requested OrketUI write-like actions for the current slice now map to shipped host routes and adopted host authority.

The only bounded caveat is `run flow`: it is shipped only as a bounded single-card issue-target run-acceptance slice, not as a general multi-node flow-execution authority.

## Action inventory

### `create card`

1. Current shipped host seam: `POST /v1/cards`
2. Canonical host contract: [docs/specs/CARD_AUTHORING_SURFACE_V1.md](docs/specs/CARD_AUTHORING_SURFACE_V1.md)
3. Current status: shipped and admitted
4. Truth note: host create success begins only when the response returns the canonical `card_id` and `revision_id`; issue-target cards also upsert the bounded runtime projection at `config/epics/orket_ui_authored_cards.json`

### `save card`

1. Current shipped host seam: `PUT /v1/cards/{card_id}`
2. Canonical host contract: [docs/specs/CARD_AUTHORING_SURFACE_V1.md](docs/specs/CARD_AUTHORING_SURFACE_V1.md)
3. Current status: shipped and admitted
4. Truth note: the optional `expected_revision_id` guard is the fail-closed stale-save boundary, and successful issue-target saves refresh the bounded runtime projection used by the admitted flow-run slice

### `validate card`

1. Current shipped host seam: `POST /v1/cards/validate`
2. Canonical host contract: [docs/specs/CARD_AUTHORING_SURFACE_V1.md](docs/specs/CARD_AUTHORING_SURFACE_V1.md)
3. Current status: shipped and admitted
4. Truth note: validation is non-persisting and does not mint host identifiers

### `save flow`

1. Current shipped host seam: `POST /v1/flows` and `PUT /v1/flows/{flow_id}`
2. Canonical host contract: [docs/specs/FLOW_AUTHORING_SURFACE_V1.md](docs/specs/FLOW_AUTHORING_SURFACE_V1.md)
3. Current status: shipped and admitted
4. Truth note: flow persistence is now host-owned for the admitted neutral flow-definition surface

### `validate flow`

1. Current shipped host seam: `POST /v1/flows/validate`
2. Canonical host contract: [docs/specs/FLOW_AUTHORING_SURFACE_V1.md](docs/specs/FLOW_AUTHORING_SURFACE_V1.md)
3. Current status: shipped and admitted
4. Truth note: validation is non-persisting and remains distinct from save truth

### `run flow`

1. Current shipped host seam: `POST /v1/flows/{flow_id}/runs`
2. Canonical host contract: [docs/specs/FLOW_AUTHORING_SURFACE_V1.md](docs/specs/FLOW_AUTHORING_SURFACE_V1.md)
3. Nearby existing seam: `POST /v1/system/run-active` remains the canonical run or rerun action for the existing Card Viewer/Runner slice only
4. Current status: shipped and admitted for the bounded current slice
5. Truth note: `200` plus returned `session_id` is authoritative run acceptance only; later run completion remains governed by the existing runtime policy and epic environment

## Nearby surfaces that do not solve the blocker

The following existing routes are not valid shortcuts for OrketUI write authority:

1. `POST /v1/cards/archive`
2. `POST /v1/system/save`
3. generic extension-runtime capability routes under `/v1/extensions/{extension_id}/runtime/*`

They do not admit the card-authoring or flow-authoring semantics this lane needs.

## Current lane consequence

The OrketUI lane may now truthfully claim host-confirmed success for:

1. card create
2. card save
3. card validation
4. flow create and save
5. flow validation
6. bounded flow-run acceptance

The lane must still not claim:

1. broader multi-node flow-execution authority than the admitted single-card issue-target slice
2. downstream run completion from flow-run acceptance alone
3. host success for extension-local draft state before the admitted host seam confirms it

## Future reopen gate

Future OrketUI expansion beyond the bounded shipped slice must reopen as a new explicit roadmap lane rather than silently broadening these admitted write claims.
