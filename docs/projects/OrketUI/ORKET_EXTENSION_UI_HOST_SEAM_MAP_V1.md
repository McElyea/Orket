# ORKET_EXTENSION_UI_HOST_SEAM_MAP_V1

Last updated: 2026-04-09
Status: Active shipped provenance support doc
Authority status: Active Orket-side shipped provenance support doc. Subordinate to shipped host authority and not itself a new host-seam grant.
Owner: Orket Core
Related docs: [docs/projects/archive/OrketUI/OUI04092026-LANE-CLOSEOUT/CLOSEOUT.md](docs/projects/archive/OrketUI/OUI04092026-LANE-CLOSEOUT/CLOSEOUT.md), [ORKET_EXTENSION_UI_REQUIREMENTS_V1.md](docs/projects/OrketUI/ORKET_EXTENSION_UI_REQUIREMENTS_V1.md), [ORKET_EXTENSION_UI_OBJECT_MODEL_V1.md](docs/projects/OrketUI/ORKET_EXTENSION_UI_OBJECT_MODEL_V1.md), [ORKET_EXTENSION_UI_WRITE_SEAM_INVENTORY_V1.md](docs/projects/OrketUI/ORKET_EXTENSION_UI_WRITE_SEAM_INVENTORY_V1.md), [docs/specs/CARD_AUTHORING_SURFACE_V1.md](docs/specs/CARD_AUTHORING_SURFACE_V1.md), [docs/specs/FLOW_AUTHORING_SURFACE_V1.md](docs/specs/FLOW_AUTHORING_SURFACE_V1.md), [docs/API_FRONTEND_CONTRACT.md](docs/API_FRONTEND_CONTRACT.md), [docs/specs/CARD_VIEWER_RUNNER_SURFACE_V1.md](docs/specs/CARD_VIEWER_RUNNER_SURFACE_V1.md), [docs/specs/COMPANION_UI_MVP_CONTRACT.md](docs/specs/COMPANION_UI_MVP_CONTRACT.md), [docs/specs/PROMPT_REFORGER_GENERIC_SERVICE_CONTRACT.md](docs/specs/PROMPT_REFORGER_GENERIC_SERVICE_CONTRACT.md), [CURRENT_AUTHORITY.md](CURRENT_AUTHORITY.md)

## Purpose

Name the allowed canonical host seams an OrketUI extension may consume without first extracting new core specs.

This doc exists so the OrketUI lane does not quietly invent host truth through BFF convenience, inferred routes, private runtime access, or old prototype knowledge.

## Authority precedence

When this doc conflicts with current shipped host authority, the higher-precedence sources are:

1. [CURRENT_AUTHORITY.md](CURRENT_AUTHORITY.md)
2. [docs/API_FRONTEND_CONTRACT.md](docs/API_FRONTEND_CONTRACT.md)
3. active host specs named by the current authority snapshot, including [docs/specs/CARD_VIEWER_RUNNER_SURFACE_V1.md](docs/specs/CARD_VIEWER_RUNNER_SURFACE_V1.md) and [docs/specs/PROMPT_REFORGER_GENERIC_SERVICE_CONTRACT.md](docs/specs/PROMPT_REFORGER_GENERIC_SERVICE_CONTRACT.md)

This doc does not reopen or override those surfaces.

## Boundary posture

1. The browser-facing product surface belongs to the extension UI and its BFF.
2. The extension BFF may translate, aggregate, cache, or normalize admitted host responses.
3. The extension BFF must not create a hidden second authority for runtime truth, card truth, run truth, artifact truth, or Prompt Reforger service-result truth.
4. The browser must not call private host internals directly.
5. Companion-style precedent applies: the outward product route family belongs to the BFF, while host capability and runtime surfaces stay behind admitted host routes.

Companion provides a real external-extension precedent for:

1. separate-repo extension ownership
2. BFF-owned `/api/*` product routes
3. translation to the generic host runtime surface under `/v1/extensions/{extension_id}/runtime/*`

That precedent does not authorize OrketUI-specific nouns, routes, or host write semantics by analogy alone.

## Allowed canonical host docs

Without new core work, the extension may rely only on host inputs already admitted by canonical docs such as:

1. [docs/API_FRONTEND_CONTRACT.md](docs/API_FRONTEND_CONTRACT.md)
2. [docs/specs/CARD_VIEWER_RUNNER_SURFACE_V1.md](docs/specs/CARD_VIEWER_RUNNER_SURFACE_V1.md)
3. [docs/specs/CARD_AUTHORING_SURFACE_V1.md](docs/specs/CARD_AUTHORING_SURFACE_V1.md)
4. [docs/specs/FLOW_AUTHORING_SURFACE_V1.md](docs/specs/FLOW_AUTHORING_SURFACE_V1.md)
5. [docs/specs/PROMPT_REFORGER_GENERIC_SERVICE_CONTRACT.md](docs/specs/PROMPT_REFORGER_GENERIC_SERVICE_CONTRACT.md)
6. host-current seams named in [CURRENT_AUTHORITY.md](CURRENT_AUTHORITY.md)

Older UI code, prototype HTML, generated mockups, and remembered route shapes are not authority.

## Shipped OrketUI host specs

The OrketUI lane now has shipped host specs for the bounded current write slice in:

1. [docs/specs/CARD_AUTHORING_SURFACE_V1.md](docs/specs/CARD_AUTHORING_SURFACE_V1.md)
2. [docs/specs/FLOW_AUTHORING_SURFACE_V1.md](docs/specs/FLOW_AUTHORING_SURFACE_V1.md)

Those specs are now adopted into the active host authority set.

## Allowed canonical host routes and events

The extension BFF may consume only admitted host routes and events that are already canonical for the needed behavior.

### Health and system visibility baseline

1. `GET /health`
2. `GET /v1/version`
3. `GET /v1/system/heartbeat`
4. `GET /v1/system/provider-status`
5. `GET /v1/system/health-view`
6. `WS /ws/events`

### Run control and run inspection baseline

1. `POST /v1/system/run-active`
2. `GET /v1/runs`
3. `GET /v1/runs/view`
4. `GET /v1/runs/{session_id}`
5. `GET /v1/runs/{session_id}/view`
6. `GET /v1/runs/{session_id}/metrics`
7. `GET /v1/runs/{session_id}/token-summary`
8. `GET /v1/runs/{session_id}/replay`
9. `GET /v1/runs/{session_id}/backlog`
10. `GET /v1/runs/{session_id}/execution-graph`

### Session and interaction baseline

1. `POST /v1/interactions/sessions`
2. `POST /v1/interactions/{session_id}/turns`
3. `POST /v1/interactions/{session_id}/finalize`
4. `POST /v1/interactions/{session_id}/cancel`
5. `GET /v1/sessions/{session_id}`
6. `GET /v1/sessions/{session_id}/status`
7. `GET /v1/sessions/{session_id}/replay`
8. `GET /v1/sessions/{session_id}/snapshot`
9. `POST /v1/sessions/{session_id}/halt`
10. `WS /ws/interactions/{session_id}`

### Card and operator-view baseline

1. `GET /v1/cards`
2. `GET /v1/cards/view`
3. `GET /v1/cards/{card_id}`
4. `GET /v1/cards/{card_id}/view`
5. `GET /v1/cards/{card_id}/history`
6. `GET /v1/cards/{card_id}/guard-history`
7. `GET /v1/cards/{card_id}/comments`
8. `POST /v1/cards`
9. `PUT /v1/cards/{card_id}`
10. `POST /v1/cards/validate`

The card read surfaces remain inspection and read-model surfaces.
The three card-authoring routes above are now the admitted write seams for create, save, and validation.

### Flow authoring baseline

1. `GET /v1/flows`
2. `GET /v1/flows/{flow_id}`
3. `POST /v1/flows`
4. `PUT /v1/flows/{flow_id}`
5. `POST /v1/flows/validate`
6. `POST /v1/flows/{flow_id}/runs`

The current admitted flow-run slice is bounded:

1. persisted flow definitions use neutral node kinds only
2. run initiation currently requires exactly one `card` node
3. run initiation does not admit `branch` or `merge`
4. the assigned card must already exist on the host card surface
5. the assigned card must resolve on the canonical run-card surface
6. the assigned card must resolve to the `issue` runtime target
7. `200` plus returned `session_id` is authoritative run acceptance only; later run completion remains governed by the existing runtime policy and epic environment

### Generic extension-runtime baseline

Where the extension needs already-admitted host runtime capabilities, it may consume the generic extension-runtime route family under:

1. `GET /v1/extensions/{extension_id}/runtime/status`
2. `GET /v1/extensions/{extension_id}/runtime/models`
3. `POST /v1/extensions/{extension_id}/runtime/llm/generate`
4. `POST /v1/extensions/{extension_id}/runtime/memory/query`
5. `POST /v1/extensions/{extension_id}/runtime/memory/write`
6. `POST /v1/extensions/{extension_id}/runtime/memory/clear`
7. `GET /v1/extensions/{extension_id}/runtime/voice/state`
8. `POST /v1/extensions/{extension_id}/runtime/voice/control`
9. `POST /v1/extensions/{extension_id}/runtime/voice/transcribe`
10. `GET /v1/extensions/{extension_id}/runtime/tts/voices`
11. `POST /v1/extensions/{extension_id}/runtime/tts/synthesize`

This remains host-owned capability behavior behind the BFF. It does not authorize direct browser calls to host routes.

These admitted generic extension-runtime routes also do not, by themselves, authorize card-authoring or flow-authoring semantics for OrketUI.

## Prompt Reforger seam note

Prompt Reforger already has a host-owned service contract in [docs/specs/PROMPT_REFORGER_GENERIC_SERVICE_CONTRACT.md](docs/specs/PROMPT_REFORGER_GENERIC_SERVICE_CONTRACT.md).

What is already canonical:

1. result classes such as `certified`, `certified_with_limits`, and `unsupported`
2. request and result envelope semantics for the generic service
3. truth rules for service-result authority

What is not yet frozen here as canonical frontend surface:

1. a dedicated Prompt Reforger UI route family
2. a canonical Prompt Reforger tab read model
3. a host-owned comparison-page payload optimized for this extension UI

If the future UI needs those as host seams, new core specs must be extracted first.

## Forbidden private or inferred seams

The extension BFF must not treat any of the following as host authority:

1. private core routes not named in canonical docs
2. direct database access
3. direct filesystem scraping as a substitute for admitted host APIs
4. inferred route families from older UI code or historical product surfaces
5. prototype HTML, mockup labels, or generated code as route-contract authority
6. historical nouns such as `rocks`, `orphanedEpics`, or `orphanedIssues` as proof of current host contracts
7. websocket field guesses that are not backed by current canonical event or API authority

If a required input is not on an admitted seam, the truthful next step is new core spec extraction, not BFF invention.

## Host-confirmed versus optimistic UI state

1. The UI may keep local draft, loading, optimistic, or selected-object state in the extension layer.
2. The BFF must label local optimistic state as extension-local until the canonical host seam confirms the operation.
3. Host-confirmed state begins only when an admitted host route or event returns or records the authoritative result.
4. The UI must preserve host identifiers from confirmed host payloads and must not replace them with projection-only IDs.
5. The UI must not narrate host success from local intent alone.

## Product actions now bound to admitted seams

This lane names product actions such as:

1. `create card`
2. `save card`
3. `validate card`
4. `save flow`
5. `validate flow`
6. `run flow`

Those actions now map to admitted host seams for the bounded shipped slice.

That does not authorize the UI to imply broader behavior than the current host contract actually ships, especially for multi-node flow execution beyond the admitted single-card issue-target run path.

The current action-by-action result for that inventory is recorded in [ORKET_EXTENSION_UI_WRITE_SEAM_INVENTORY_V1.md](docs/projects/OrketUI/ORKET_EXTENSION_UI_WRITE_SEAM_INVENTORY_V1.md).

## Change gate for implementation

If a proposed UI feature depends on host data or actions outside this seam map, the feature is blocked on new core spec extraction or explicit host-surface expansion first.
