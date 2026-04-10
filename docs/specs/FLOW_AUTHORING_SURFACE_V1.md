# Flow Authoring Surface V1

Last updated: 2026-04-09
Status: Active shipped authority
Owner: Orket Core
Source requirements: [docs/projects/OrketUI/ORKET_EXTENSION_UI_REQUIREMENTS_V1.md](docs/projects/OrketUI/ORKET_EXTENSION_UI_REQUIREMENTS_V1.md)
Related docs: [docs/projects/archive/OrketUI/OUI04092026-LANE-CLOSEOUT/CLOSEOUT.md](docs/projects/archive/OrketUI/OUI04092026-LANE-CLOSEOUT/CLOSEOUT.md), [docs/projects/OrketUI/ORKET_EXTENSION_UI_OBJECT_MODEL_V1.md](docs/projects/OrketUI/ORKET_EXTENSION_UI_OBJECT_MODEL_V1.md), [docs/projects/OrketUI/ORKET_EXTENSION_UI_WRITE_SEAM_INVENTORY_V1.md](docs/projects/OrketUI/ORKET_EXTENSION_UI_WRITE_SEAM_INVENTORY_V1.md), [docs/API_FRONTEND_CONTRACT.md](docs/API_FRONTEND_CONTRACT.md), [CURRENT_AUTHORITY.md](CURRENT_AUTHORITY.md)

## 1. Purpose

Define the bounded current host surface for persisted flow definitions, flow validation, and flow-run initiation required by OrketUI and any later host-agnostic flow authoring client.

This spec is current shipped host authority for the mounted routes below.

## 2. Boundary and authority

1. Host owns canonical `flow_id`, persisted flow truth, revision truth, validation truth, and run acceptance truth for the current admitted slice.
2. The extension UI owns unsaved canvas layout, local selection, local draft composition, and Sequencer presentation state before host confirmation.
3. The extension BFF may shape host responses for the browser, but it must not mint host flow ids, revision ids, or run success.
4. Host node semantics remain neutral. UI palette labels such as `Requirement Card`, `Code Card`, `Critique Card`, and `Approval Card` remain extension-local projections over host-neutral flow nodes plus assigned card metadata.

## 3. Canonical routes

1. `GET /v1/flows`
2. `GET /v1/flows/{flow_id}`
3. `POST /v1/flows`
4. `PUT /v1/flows/{flow_id}`
5. `POST /v1/flows/validate`
6. `POST /v1/flows/{flow_id}/runs`

## 4. Canonical flow models

### `FlowDefinitionWriteModel`

Must include at least:

1. `name`
2. `description`
3. `nodes`
4. `edges`

### `FlowNodeWriteModel`

Must include at least:

1. `node_id`
2. `kind`
3. `label`
4. `assigned_card_id`
5. `notes`

The only host-neutral node kinds admitted by this spec are:

1. `start`
2. `card`
3. `branch`
4. `merge`
5. `final`

### `FlowEdgeWriteModel`

Must include at least:

1. `edge_id`
2. `from_node_id`
3. `to_node_id`
4. `condition_label`

### `FlowValidationResult`

Must return at least:

1. `is_valid`
2. `errors`
3. `warnings`
4. `summary`
5. `reason_codes`

### `FlowWriteResult`

Must return at least:

1. `flow_id`
2. `revision_id`
3. `saved_at`
4. `validation`
5. `degraded`
6. `summary`
7. `reason_codes`

### `FlowRunAccepted`

Must return at least:

1. `flow_id`
2. `revision_id`
3. `session_id`
4. `accepted_at`
5. `summary`

## 5. Truth rules

1. `POST /v1/flows` mints the canonical host `flow_id` and the first `revision_id`.
2. `PUT /v1/flows/{flow_id}` is the authoritative save surface for an existing flow and should support an optional `expected_revision_id` guard so stale saves fail closed with `revision_conflict`.
3. `POST /v1/flows/validate` is non-persisting. It must not mutate durable state or mint a host `flow_id` when the caller is validating an unsaved draft.
4. `POST /v1/flows/{flow_id}/runs` requires a persisted `flow_id`. It must not accept projection-only or unsaved local draft state as host execution truth.
5. `POST /v1/flows/{flow_id}/runs` should support an optional `expected_revision_id` guard so execution fails closed when the caller is acting on stale saved state.
6. Successful flow-run acceptance returns the canonical `session_id` and hands off later inspection to the existing run and session read surfaces.
7. The current admitted run slice is intentionally bounded: exactly one `card` node, no `branch` or `merge`, assigned card present on the host card surface, assigned card resolvable on the canonical run-card surface, and assigned card resolvable to the `issue` runtime target.
8. `200` on `POST /v1/flows/{flow_id}/runs` is authoritative acceptance only. Downstream run completion remains governed by the existing runtime policy and epic environment after handoff.
9. The current admitted run slice composes with cards created or updated through [docs/specs/CARD_AUTHORING_SURFACE_V1.md](docs/specs/CARD_AUTHORING_SURFACE_V1.md) because issue-type authored cards are projected onto the canonical run-card surface before flow-run acceptance resolves assigned cards.

## 6. Mounted current slice

1. The routes above are mounted through [orket/interfaces/routers/flows.py](orket/interfaces/routers/flows.py) and included by [orket/interfaces/api.py](orket/interfaces/api.py).
2. Flow persistence now uses the canonical durable path `.orket/durable/db/orket_ui_flows.sqlite3` via [orket/runtime_paths.py](orket/runtime_paths.py).
3. The neutral host node kinds above do not promote UI palette labels into host truth.
4. `GET /v1/flows` and `GET /v1/flows/{flow_id}` are now canonical host inspection surfaces for persisted flow definitions.
5. The bounded run-composition path may resolve assigned cards through the authored-card runtime projection maintained by [docs/specs/CARD_AUTHORING_SURFACE_V1.md](docs/specs/CARD_AUTHORING_SURFACE_V1.md).

## 7. Sync rule

When this surface changes, update in the same change:

1. [docs/specs/FLOW_AUTHORING_SURFACE_V1.md](docs/specs/FLOW_AUTHORING_SURFACE_V1.md)
2. [docs/API_FRONTEND_CONTRACT.md](docs/API_FRONTEND_CONTRACT.md)
3. [CURRENT_AUTHORITY.md](CURRENT_AUTHORITY.md)
4. [docs/projects/OrketUI/ORKET_EXTENSION_UI_HOST_SEAM_MAP_V1.md](docs/projects/OrketUI/ORKET_EXTENSION_UI_HOST_SEAM_MAP_V1.md)
5. [docs/projects/OrketUI/ORKET_EXTENSION_UI_OBJECT_MODEL_V1.md](docs/projects/OrketUI/ORKET_EXTENSION_UI_OBJECT_MODEL_V1.md)
