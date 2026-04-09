# ORKET_EXTENSION_UI_OBJECT_MODEL_V1

Last updated: 2026-04-09
Status: Draft staged future-lane support doc
Authority status: Staging only. Not current implementation authority until explicitly adopted.
Owner: Orket Core
Related docs: [ORKET_EXTENSION_UI_REQUIREMENTS_V1.md](docs/projects/future/OrketUI/ORKET_EXTENSION_UI_REQUIREMENTS_V1.md), [ORKET_EXTENSION_UI_HOST_SEAM_MAP_V1.md](docs/projects/future/OrketUI/ORKET_EXTENSION_UI_HOST_SEAM_MAP_V1.md), [docs/API_FRONTEND_CONTRACT.md](docs/API_FRONTEND_CONTRACT.md), [docs/specs/CARD_VIEWER_RUNNER_SURFACE_V1.md](docs/specs/CARD_VIEWER_RUNNER_SURFACE_V1.md), [docs/specs/PROMPT_REFORGER_GENERIC_SERVICE_CONTRACT.md](docs/specs/PROMPT_REFORGER_GENERIC_SERVICE_CONTRACT.md), [CURRENT_AUTHORITY.md](CURRENT_AUTHORITY.md)

## Purpose

Split the Orket UI lane into:

1. host-owned nouns already backed by canonical host surfaces
2. extension-owned projections that the UI may use only as derived constructs

This doc exists so the future UI lane does not silently promote projection vocabulary into host truth.

## Authority precedence

When this doc conflicts with current shipped host authority, the higher-precedence sources are:

1. [CURRENT_AUTHORITY.md](CURRENT_AUTHORITY.md)
2. [docs/API_FRONTEND_CONTRACT.md](docs/API_FRONTEND_CONTRACT.md)
3. active host specs already named by current authority

This doc is staging-only and does not claim new shipped host contracts.

## Host-owned nouns already supported by canonical surfaces

The following nouns are safe to treat as host-owned because they already exist on current canonical host docs or specs:

1. `run`
2. `session_id`
3. interaction session and interaction turn surfaces exposed through the admitted session and interaction APIs
4. websocket event streams exposed through `WS /ws/events` and `WS /ws/interactions/{session_id}`
5. card and run operator-view read models already admitted by [docs/specs/CARD_VIEWER_RUNNER_SURFACE_V1.md](docs/specs/CARD_VIEWER_RUNNER_SURFACE_V1.md)
6. host route families and route parameters already fixed by [docs/API_FRONTEND_CONTRACT.md](docs/API_FRONTEND_CONTRACT.md)
7. Prompt Reforger service-result classes and result-envelope semantics already fixed by [docs/specs/PROMPT_REFORGER_GENERIC_SERVICE_CONTRACT.md](docs/specs/PROMPT_REFORGER_GENERIC_SERVICE_CONTRACT.md)

Where a host view model already exists, the extension should prefer that read model over raw payload invention.

## Extension-owned projections

Until core specs explicitly freeze them as host contracts, the following should be treated as extension-owned projections rather than host truth:

1. `flow`
2. `display_category`
3. `expected_output_type`
4. `approval_expectation`
5. `artifact_expectation`
6. `epic` as a UI object
7. `phase` as a UI object
8. `Requirement Card`
9. `Code Card`
10. `Critique Card`
11. `Approval Card`
12. Sequencer palette nouns such as `Start`, `Branch`, `Merge`, and `Final`
13. tab-local layout objects such as board columns, right-panel inspector groupings, and selected-item shells

These may be useful UI constructs. They are not host truth merely because earlier exploratory UI work used similar words.

## Derivation rules for extension-owned projections

1. Every projection that represents or summarizes host data must preserve the source host identifier or artifact reference it came from.
2. Projection fields must remain recognizable as derived when they do not exist on the host surface.
3. A derived label must not replace the underlying host value when the host value is available.
4. Multiple host sources may be aggregated into one projection only when the projection records enough source mapping to trace back to those inputs.
5. If a projection cannot be traced back to admitted host inputs, it is not safe as authoritative UI state.

## Persistence truth rules

1. Host-owned persistence truth exists only when an admitted host seam confirms it.
2. Extension-local drafts, preferences, selection state, and projection layout state may be persisted by the extension, but they must remain clearly extension-owned.
3. The extension BFF must not claim that a host-owned object was created, saved, updated, or accepted unless the host seam confirmed that outcome.
4. When extension-local persistence is used, the UI must not blur it with host persistence or host execution truth.

## Identifier rules

1. Host identifiers remain host authority and must be preserved exactly as received.
2. Extension-owned projections may use extension-local identifiers, but those IDs must not masquerade as host IDs.
3. A projection should carry both its extension-local ID and its host source reference when both exist.
4. Derived IDs must never be the only remaining way to trace back to host truth.

## Save and run conflict rules

1. If the UI contains unsaved extension-local edits, the UI must distinguish between extension-local draft state and the last host-confirmed state.
2. A run action must not imply host execution against unsaved or projection-only state when the host has not admitted that state.
3. If a future feature requires running extension-owned flow projections as host truth, new core seams must be specified first.
4. When a user can act on stale host-confirmed data after local edits exist, the UI must make that distinction explicit instead of pretending both states are the same.
5. Conflicts between host-confirmed state and extension-local draft state must fail closed to explicit user-visible choice, not silent overwrite.

## Prompt Reforger object-model note

Prompt Reforger service truth already owns:

1. request tuple semantics
2. result classes
3. service-run result authority

The extension UI may add derived comparison shells such as:

1. candidate comparison panes
2. diff groupings
3. selected preferred-result focus

Those UI constructs remain extension-owned projections unless future core docs freeze a host read model for them.

## Change gate for future implementation

If a planned UI feature requires treating an extension-owned projection as canonical host truth, the truthful next step is extracting a new core spec first.
