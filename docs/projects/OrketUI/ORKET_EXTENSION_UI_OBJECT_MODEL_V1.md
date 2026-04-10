# ORKET_EXTENSION_UI_OBJECT_MODEL_V1

Last updated: 2026-04-09
Status: Active shipped provenance support doc
Authority status: Active Orket-side shipped provenance support doc. Summarizes current host-owned nouns and remaining extension-owned projections, but does not itself create new host authority.
Owner: Orket Core
Related docs: [docs/projects/archive/OrketUI/OUI04092026-LANE-CLOSEOUT/CLOSEOUT.md](docs/projects/archive/OrketUI/OUI04092026-LANE-CLOSEOUT/CLOSEOUT.md), [ORKET_EXTENSION_UI_REQUIREMENTS_V1.md](docs/projects/OrketUI/ORKET_EXTENSION_UI_REQUIREMENTS_V1.md), [ORKET_EXTENSION_UI_HOST_SEAM_MAP_V1.md](docs/projects/OrketUI/ORKET_EXTENSION_UI_HOST_SEAM_MAP_V1.md), [docs/specs/CARD_AUTHORING_SURFACE_V1.md](docs/specs/CARD_AUTHORING_SURFACE_V1.md), [docs/specs/FLOW_AUTHORING_SURFACE_V1.md](docs/specs/FLOW_AUTHORING_SURFACE_V1.md), [docs/API_FRONTEND_CONTRACT.md](docs/API_FRONTEND_CONTRACT.md), [docs/specs/CARD_VIEWER_RUNNER_SURFACE_V1.md](docs/specs/CARD_VIEWER_RUNNER_SURFACE_V1.md), [docs/specs/PROMPT_REFORGER_GENERIC_SERVICE_CONTRACT.md](docs/specs/PROMPT_REFORGER_GENERIC_SERVICE_CONTRACT.md), [CURRENT_AUTHORITY.md](CURRENT_AUTHORITY.md)

## Purpose

Split the OrketUI lane into:

1. host-owned nouns already backed by canonical host surfaces
2. extension-owned projections that the UI may use only as derived constructs

This doc exists so the OrketUI lane does not silently promote projection vocabulary into host truth.

## Authority precedence

When this doc conflicts with current shipped host authority, the higher-precedence sources are:

1. [CURRENT_AUTHORITY.md](CURRENT_AUTHORITY.md)
2. [docs/API_FRONTEND_CONTRACT.md](docs/API_FRONTEND_CONTRACT.md)
3. active host specs already named by current authority

This doc is an active shipped provenance support doc and remains subordinate to shipped host authority.

## Host-owned nouns already supported by canonical surfaces

The following nouns are safe to treat as host-owned because they already exist on current canonical host docs or specs:

1. `run`
2. `session_id`
3. `card_id`
4. card authoring `revision_id`
5. `flow`
6. `flow_id`
7. flow authoring `revision_id`
8. interaction session and interaction turn surfaces exposed through the admitted session and interaction APIs
9. websocket event streams exposed through `WS /ws/events` and `WS /ws/interactions/{session_id}`
10. card and run operator-view read models already admitted by [docs/specs/CARD_VIEWER_RUNNER_SURFACE_V1.md](docs/specs/CARD_VIEWER_RUNNER_SURFACE_V1.md)
11. host route families and route parameters already fixed by [docs/API_FRONTEND_CONTRACT.md](docs/API_FRONTEND_CONTRACT.md)
12. card authoring payload fields now admitted through [docs/specs/CARD_AUTHORING_SURFACE_V1.md](docs/specs/CARD_AUTHORING_SURFACE_V1.md): `display_category`, `expected_output_type`, `approval_expectation`, and `artifact_expectation`
13. neutral flow node kinds now admitted through [docs/specs/FLOW_AUTHORING_SURFACE_V1.md](docs/specs/FLOW_AUTHORING_SURFACE_V1.md): `start`, `card`, `branch`, `merge`, and `final`
14. Prompt Reforger service-result classes and result-envelope semantics already fixed by [docs/specs/PROMPT_REFORGER_GENERIC_SERVICE_CONTRACT.md](docs/specs/PROMPT_REFORGER_GENERIC_SERVICE_CONTRACT.md)

Where a host view model already exists, the extension should prefer that read model over raw payload invention.

## Extension-owned projections

Until core specs explicitly freeze them as host contracts, the following should be treated as extension-owned projections rather than host truth:

1. `epic` as a UI object
2. `phase` as a UI object
3. `Requirement Card`
4. `Code Card`
5. `Critique Card`
6. `Approval Card`
7. Sequencer palette labels and iconography layered on top of host-neutral node kinds
8. tab-local layout objects such as board columns, right-panel inspector groupings, and selected-item shells

These may be useful UI constructs. They are not host truth merely because earlier exploratory UI work used similar words.

## Shipped authoring object-model note

The OrketUI lane now has shipped host specs in:

1. [docs/specs/CARD_AUTHORING_SURFACE_V1.md](docs/specs/CARD_AUTHORING_SURFACE_V1.md)
2. [docs/specs/FLOW_AUTHORING_SURFACE_V1.md](docs/specs/FLOW_AUTHORING_SURFACE_V1.md)

Those shipped specs move the neutral host authoring nouns above into current host authority.

Sequencer palette labels such as `Requirement Card`, `Code Card`, `Critique Card`, and `Approval Card` remain extension-local projections even after that shipped adoption.

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
3. If a future feature requires broader flow-execution truth than the current admitted single-card issue-target run slice, new core seams or an expanded admitted slice must be specified first.
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

## Change gate for implementation

If a planned UI feature requires treating an extension-owned projection as canonical host truth, the truthful next step is extracting a new core spec first.

That extraction and shipped adoption are now done for the bounded current card and flow authoring slice.
Any future expansion beyond the current admitted flow-run boundary must reopen through a new explicit roadmap lane.
