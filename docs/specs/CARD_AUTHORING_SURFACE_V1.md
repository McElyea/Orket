# Card Authoring Surface V1

Last updated: 2026-04-09
Status: Active shipped authority
Owner: Orket Core
Source requirements: [docs/projects/OrketUI/ORKET_EXTENSION_UI_REQUIREMENTS_V1.md](docs/projects/OrketUI/ORKET_EXTENSION_UI_REQUIREMENTS_V1.md)
Related docs: [docs/projects/archive/OrketUI/OUI04092026-LANE-CLOSEOUT/CLOSEOUT.md](docs/projects/archive/OrketUI/OUI04092026-LANE-CLOSEOUT/CLOSEOUT.md), [docs/projects/OrketUI/ORKET_EXTENSION_UI_WRITE_SEAM_INVENTORY_V1.md](docs/projects/OrketUI/ORKET_EXTENSION_UI_WRITE_SEAM_INVENTORY_V1.md), [docs/specs/CARD_VIEWER_RUNNER_SURFACE_V1.md](docs/specs/CARD_VIEWER_RUNNER_SURFACE_V1.md), [docs/API_FRONTEND_CONTRACT.md](docs/API_FRONTEND_CONTRACT.md), [CURRENT_AUTHORITY.md](CURRENT_AUTHORITY.md)

## 1. Purpose

Define the bounded current host write surface for card creation, card save, and card validation required by OrketUI and any later host-agnostic card authoring client.

This spec is current shipped host authority for the mounted routes below.

## 2. Boundary and authority

1. Host owns canonical `card_id`, persisted card truth, revision truth, and host-confirmed validation truth.
2. The extension UI owns unsaved editor drafts, local layout, local selection, and any optimistic presentation state before host confirmation.
3. The extension BFF may shape host responses for the browser, but it must not mint host ids, revision ids, or save success.
4. Duplicate-card behavior remains a UI convenience composed from read plus create unless a later core spec extracts a dedicated host duplicate seam.

## 3. Canonical routes

1. `POST /v1/cards`
2. `PUT /v1/cards/{card_id}`
3. `POST /v1/cards/validate`

## 4. Canonical write models

### `CardDraftWriteModel`

Minimal required fields:

1. `name`
2. `purpose`
3. `card_kind`
4. `prompt`
5. `inputs`
6. `expected_outputs`
7. `expected_output_type`
8. `display_category`
9. `notes`
10. `constraints`
11. `approval_expectation`
12. `artifact_expectation`

The host may persist richer internal state, but these fields are the minimum authoring contract extracted from the OrketUI lane.

### `CardWriteResult`

Must return at least:

1. `card_id`
2. `revision_id`
3. `saved_at`
4. `validation`
5. `degraded`
6. `summary`
7. `reason_codes`

### `CardValidationResult`

Must return at least:

1. `is_valid`
2. `errors`
3. `warnings`
4. `summary`
5. `reason_codes`

`reason_codes` are machine-readable operator-facing diagnostics.
`summary` is human-readable.

## 5. Truth rules

1. `POST /v1/cards` mints the canonical host `card_id` and the first `revision_id`.
2. `PUT /v1/cards/{card_id}` is the authoritative save surface for an existing card and should support an optional `expected_revision_id` guard so stale saves fail closed with `revision_conflict`.
3. `POST /v1/cards/validate` is non-persisting. It must not mutate durable state or mint a host `card_id` when the caller is validating an unsaved draft.
4. Host-confirmed create or save success begins only when the `POST` or `PUT` response returns the authoritative `card_id` plus `revision_id`.
5. Unknown or unsupported fields must fail closed through validation or save rejection rather than being silently reinterpreted.
6. The current host implementation persists the authoring payload and revision markers through the canonical card record surface, including `authoring_payload`, `authoring_revision_id`, and `authoring_saved_at` inside host card params.
7. Extension-local card-kind labels may normalize onto existing host card types, but the original authoring label remains preserved in host authoring metadata.
8. When the authored card normalizes to the `issue` runtime target, successful create and save also upsert a bounded runtime projection at `config/epics/orket_ui_authored_cards.json` so the admitted current flow-run slice can resolve that card on the canonical run-card surface without minting a second card authority.

## 6. Mounted current slice

1. The routes above are mounted through [orket/interfaces/routers/card_authoring.py](orket/interfaces/routers/card_authoring.py) and included by [orket/interfaces/api.py](orket/interfaces/api.py).
2. The existing read and operator-view surfaces in [docs/specs/CARD_VIEWER_RUNNER_SURFACE_V1.md](docs/specs/CARD_VIEWER_RUNNER_SURFACE_V1.md) remain the canonical card inspection surface.
3. Save requests fail closed with `404` when the card does not exist and `409` on revision conflict.
4. The bounded runtime projection for issue-type authored cards is maintained through [orket/application/services/card_authoring_runtime_projection_service.py](orket/application/services/card_authoring_runtime_projection_service.py) and writes the canonical composition file at `config/epics/orket_ui_authored_cards.json`.

## 7. Sync rule

When this surface changes, update in the same change:

1. [docs/specs/CARD_AUTHORING_SURFACE_V1.md](docs/specs/CARD_AUTHORING_SURFACE_V1.md)
2. [docs/API_FRONTEND_CONTRACT.md](docs/API_FRONTEND_CONTRACT.md)
3. [CURRENT_AUTHORITY.md](CURRENT_AUTHORITY.md)
4. [docs/projects/OrketUI/ORKET_EXTENSION_UI_HOST_SEAM_MAP_V1.md](docs/projects/OrketUI/ORKET_EXTENSION_UI_HOST_SEAM_MAP_V1.md)
