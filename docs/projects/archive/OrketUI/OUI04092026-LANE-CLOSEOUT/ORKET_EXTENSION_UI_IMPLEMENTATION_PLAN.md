# OrketUI Implementation Plan

Owner: Orket Core
Status: Archived completed lane record
Last updated: 2026-04-09
Related docs: [CLOSEOUT.md](docs/projects/archive/OrketUI/OUI04092026-LANE-CLOSEOUT/CLOSEOUT.md), [docs/projects/OrketUI/ORKET_EXTENSION_UI_REQUIREMENTS_V1.md](docs/projects/OrketUI/ORKET_EXTENSION_UI_REQUIREMENTS_V1.md), [docs/projects/OrketUI/ORKET_EXTENSION_UI_HOST_SEAM_MAP_V1.md](docs/projects/OrketUI/ORKET_EXTENSION_UI_HOST_SEAM_MAP_V1.md), [docs/projects/OrketUI/ORKET_EXTENSION_UI_OBJECT_MODEL_V1.md](docs/projects/OrketUI/ORKET_EXTENSION_UI_OBJECT_MODEL_V1.md), [docs/projects/OrketUI/ORKET_EXTENSION_UI_WRITE_SEAM_INVENTORY_V1.md](docs/projects/OrketUI/ORKET_EXTENSION_UI_WRITE_SEAM_INVENTORY_V1.md), [docs/specs/CARD_AUTHORING_SURFACE_V1.md](docs/specs/CARD_AUTHORING_SURFACE_V1.md), [docs/specs/FLOW_AUTHORING_SURFACE_V1.md](docs/specs/FLOW_AUTHORING_SURFACE_V1.md), [docs/API_FRONTEND_CONTRACT.md](docs/API_FRONTEND_CONTRACT.md), [docs/specs/CARD_VIEWER_RUNNER_SURFACE_V1.md](docs/specs/CARD_VIEWER_RUNNER_SURFACE_V1.md), [docs/specs/PROMPT_REFORGER_GENERIC_SERVICE_CONTRACT.md](docs/specs/PROMPT_REFORGER_GENERIC_SERVICE_CONTRACT.md), [docs/specs/COMPANION_UI_MVP_CONTRACT.md](docs/specs/COMPANION_UI_MVP_CONTRACT.md), [CURRENT_AUTHORITY.md](CURRENT_AUTHORITY.md)

## 1. Purpose

Turn OrketUI from a future-lane packet into an active Orket-side implementation lane while keeping the extension boundary truthful.

This plan governs:

1. the live project posture for Orket-side provenance,
2. blocker removal,
3. the first admitted implementation slices,
4. the order in which write semantics may become executable.

This plan does not make core Orket the implementation authority holder for the extension source code.
The extension implementation remains a separate project.

## 2. Current truthful starting state

As of 2026-04-09, the lane starts from the following verified position:

1. Orket now carries the live OrketUI authority packet under `docs/projects/OrketUI/`.
2. The separate extension repo exists at `C:\Source\OrketUI`, and the observed repo root shows `README.md`, `pyproject.toml`, `extension.yaml`, `UI/`, `scripts/`, `src/`, `tests/`, and `stitch-design/`.
3. The observed mockup package includes `stitch-design/<tab>/screen.png` and `code.html` for `board`, `cards`, `inspector`, `prompt-reforger`, `runs`, and `sequencer`, plus `stitch-design/orket-botanical/DESIGN.md`.
4. The external repo bootstrap blocker is cleared: the repo carries the selected mockups, a top-level source-of-truth note, and a shell/BFF scaffold together.
5. The separate repo at `C:\Source\Orket-extensions\Companion` remains the real split-repo BFF precedent, but does not authorize OrketUI-specific nouns or write semantics by analogy.
6. The external repo ships a live `React + Vite + TypeScript` shell under `UI/`, and the BFF serves the built app plus admitted read-backed routes for system overview, cards, runs, detail views, and Prompt Reforger context.
7. The mockup-parity shell and tab convergence lane is now materially complete for the current slice: the shared shell, Cards, Board, Runs, Prompt Reforger, Inspector, and Sequencer now follow the selected mockup direction instead of the earlier admin-style scaffold.
8. Current admitted host seams are sufficient for the read-backed shell, cards, runs, sessions, websocket events, Prompt Reforger service truth, and the bounded current card and flow authoring surfaces.
9. The host now ships admitted card-authoring routes for `create card`, `save card`, and `validate card`.
10. The host now ships admitted flow-authoring routes for `list flow`, `get flow`, `save flow`, `validate flow`, and bounded `run flow` acceptance.
11. Live proof now succeeds for the React shell root, deep links, built assets, admitted BFF read routes, admitted host write routes, and admitted BFF write paths when Orket host is running locally with API-key auth.
12. A live proof run on 2026-04-09 returned `observed_path=primary` and `observed_result=success` for host `POST /v1/cards/validate`, `POST /v1/cards`, `PUT /v1/cards/{card_id}`, `POST /v1/flows/validate`, `POST /v1/flows`, `PUT /v1/flows/{flow_id}`, and `POST /v1/flows/{flow_id}/runs`, plus the corresponding BFF route family.
13. The current flow-run slice remains intentionally bounded: `POST /v1/flows/{flow_id}/runs` proved authoritative acceptance and returned a canonical `session_id`, but the same live proof environment later failed during downstream execution because the seeded epic lacked a required `code_reviewer` seat. That is a truthful runtime-policy caveat, not a route-admission blocker.

## 3. Governing decisions

The following decisions govern this lane unless the roadmap is explicitly changed:

1. OrketUI remains a separate extension project rather than becoming a core Orket UI.
2. This repo keeps the live roadmap, provenance, requirements, seam map, object model, and implementation plan for the lane.
3. The separate extension repo becomes the implementation authority holder only when it carries the selected mockups, a source-of-truth note or README, and an initial shell/BFF scaffold together.
4. The extension BFF remains non-authoritative. It may shape data, but it may not invent runtime truth, host persistence truth, or hidden orchestration policy.
5. The first admitted implementation slice should maximize progress on read-backed shell behavior before reopening host write semantics.
6. Any write-like UI behavior must either map to already-admitted host seams or trigger new core spec extraction first.
7. Prompt Reforger UI behavior remains subordinate to the generic service contract until a dedicated frontend read model or route family is explicitly extracted.
8. The intended OrketUI product stack is `React + Vite + TypeScript`.
9. `React Router` should be used primarily for navigation, nested layouts, selected-object URLs, and Inspector deep links, not as the primary BFF-backed data-loading system unless the lane later makes an explicit loaders/actions decision.
10. `TanStack Query` should own BFF-backed server state and any admitted write operations later.
11. `Zustand` should remain limited to extension-local UI state such as selection, rails, modal state, draft-versus-host-confirmed state, and local preferences; it should not become a second server-state cache.
12. `React Flow` should remain isolated to the Sequencer canvas so graph-editor complexity does not leak into the rest of the shell.
13. `Radix UI` should provide primitive UI building blocks.
14. `CodeMirror` is the default editor choice for card and prompt editing; `Monaco` should be introduced only if the lane later proves it needs IDE-grade editor services.
15. Mockup-parity shell and tab convergence should happen before the write-surface implementation lane wherever the remaining work is extension-local and can be driven by the admitted read-backed slice plus extension-local draft state.
16. The current `run flow` authority is bounded to accepted single-card issue-target execution initiation; broader multi-node flow execution requires later host expansion.

## 4. Lane objective

This lane is complete only when all of the following are true:

1. the separate OrketUI repo meets the implementation-authority-holder condition,
2. the extension ships a working shell with the required top-level tabs,
3. read-backed UI behavior proves itself against admitted host seams,
4. each implemented write action has host-seam proof or an extracted new core spec,
5. Orket host remains UI-agnostic,
6. Orket-side provenance docs and roadmap remain aligned with what is actually implemented.

## 5. Non-goals

This lane does not aim to:

1. move the UI shell into core Orket,
2. let the BFF become a second runtime authority,
3. treat mockup HTML as implementation truth,
4. claim write behavior before host seam proof exists,
5. silently promote extension projection nouns into host contracts.

## 6. Workstream order

## Workstream 0 - Promote OrketUI to a live project in Orket

### Goal

Make OrketUI a live project lane in this repo with one canonical implementation plan.

### Tasks

1. move the OrketUI docs out of `docs/projects/future/OrketUI/` and into `docs/projects/OrketUI/`
2. create one canonical implementation plan for the lane
3. put the lane on `docs/ROADMAP.md` under `Priority Now`
4. add the live project folder to the roadmap project index

### Exit criteria

1. `docs/projects/OrketUI/` exists as the canonical non-archive project path
2. `docs/ROADMAP.md` points `Priority Now` at this plan, not at the requirements doc
3. no active OrketUI project doc remains parked under `docs/projects/future/`

### Current checkpoint

This workstream is completed.

## Workstream 1 - External repo authority bootstrap

### Goal

Remove blocker 1 by making the separate OrketUI repo a real implementation authority holder.

### Tasks

1. keep the external project rooted at `C:\Source\OrketUI`
2. retain the selected `stitch-design/` mockup package there
3. add a top-level README or source-of-truth note that names:
   - requirements truth,
   - mockup truth,
   - implementation truth,
   - the split-repo authority posture,
   - local development entrypoints
4. add an initial shell/BFF scaffold in the external repo
5. make the scaffold own browser-facing product routes while preserving host-only seams behind the BFF

### Exit criteria

1. the external repo visibly contains the mockup package, the source-of-truth note or README, and the shell/BFF scaffold together
2. the external repo can boot the UI shell without claiming nonexistent host write semantics

### Current checkpoint

Workstream 1 is completed.

## Workstream 2 - Read-backed shell and BFF first slice

### Goal

Ship the first truthful implementation slice without waiting on new host write seams.

### Tasks

1. implement the desktop shell and top-level tabs in the external repo
2. replace the bootstrap shell with a `React + Vite + TypeScript` app in the external repo while preserving the same BFF boundary
3. use `React Router` mainly for tab routing, nested layouts, selected-object URLs, and Inspector deep links
4. use `TanStack Query` for BFF-backed read models instead of creating a second route-loader cache layer
5. use `Zustand` only for extension-local UI state
6. implement the BFF against only the admitted host seams named in [ORKET_EXTENSION_UI_HOST_SEAM_MAP_V1.md](docs/projects/OrketUI/ORKET_EXTENSION_UI_HOST_SEAM_MAP_V1.md)
7. build Cards, Runs, Board, Inspector, and Prompt Reforger around read-backed host inputs first
8. keep Sequencer isolated around `React Flow` as an extension-owned composition surface without pretending host persistence truth exists
9. start card and prompt editing with `CodeMirror` unless a later lane decision proves `Monaco` is necessary
10. preserve host-confirmed versus extension-local state boundaries in the UI
11. keep host identifiers intact in all BFF read models

### Exit criteria

1. the shell runs through the external BFF
2. the first slice proves read-backed behavior against admitted host routes or events
3. no view requires private routes, direct DB reads, or inferred seams
4. the product shell uses the explicit frontend stack decision instead of the temporary bootstrap scaffold

### Current checkpoint

Workstream 2 is completed.

The external repo now ships:

1. a `React + Vite + TypeScript` shell under `UI/`
2. `React Router` for shell routing and deep links
3. `TanStack Query` for BFF-backed read models
4. `Zustand` for extension-local UI selection and shell state
5. `React Flow` on the Sequencer draft surface
6. `CodeMirror` on bounded card, inspector, and Prompt Reforger text surfaces
7. a BFF that reads only admitted host surfaces for system overview, cards, runs, card detail, run detail, and bounded Prompt Reforger context

## Workstream 3 - Mockup-parity shell and tab convergence

### Goal

Bring the shipped OrketUI shell and major tabs into deliberate visual convergence with the selected Stitch mockups before reopening the host write-surface lane.

### Tasks

1. use `stitch-design/<tab>/screen.png` as the primary visual reference for Cards, Board, Runs, Inspector, Prompt Reforger, and Sequencer
2. converge the shared shell on the intended cream-and-emerald visual system, typography, spacing, and panel proportions
3. converge the left rail, top-level tab treatment, inspector behavior, and desktop-first layout structure with the selected mockups
4. bring each current read-backed tab as close to the selected mockup as current admitted host seams allow without inventing write behavior
5. keep any controls that depend on unshipped write seams visually present only when they remain truthful about blocked or draft-only behavior
6. preserve the BFF boundary, admitted read-model posture, and host-confirmed versus extension-local state distinctions while converging the design
7. record any mockup element that cannot yet match because it depends on an unshipped host seam

### Exit criteria

1. the shared shell materially matches the selected mockup direction instead of reading like a bootstrap admin scaffold
2. Cards, Board, Runs, Inspector, Prompt Reforger, and Sequencer each materially match their selected mockup structure where current read seams already allow it
3. any still-unmatched areas are explicitly attributable to unshipped host seams or bounded implementation gaps rather than drift or neglect

### Current checkpoint

Workstream 3 is completed.

The external repo now uses the selected prototype families to drive the shipped layout split:

1. `orket_studio_prototype.html` for Cards, Board, Runs, and Prompt Reforger
2. `orket_system_architect_prototype.html` for Sequencer and Inspector

Live proof for this slice included:

1. `npm run build` in `C:\Source\OrketUI\UI`
2. the external BFF serving the built shell
3. browser renders for Cards, Board, Prompt Reforger, and Sequencer after hydration through the running BFF

## Workstream 4 - Write-seam inventory and core spec extraction

### Goal

Prove or extract every write-like host seam the UI needs.

### Tasks

1. inventory each requested write action:
   - `create card`
   - `save card`
   - `validate card`
   - `save flow`
   - `validate flow`
   - `run flow`
2. map each action to an already-admitted host seam when one exists
3. for each gap, extract a new core spec before implementation claims are made
4. if a shipped host contract changes, update the canonical host docs in the same change
5. define host-confirmed versus optimistic state rules for each admitted write action

### Exit criteria

1. every intended write action is either backed by current host authority, bound to an extracted core spec, or explicitly deferred
2. no OrketUI write behavior remains in a fuzzy middle state between product intent and admitted host truth

### Current checkpoint

Workstream 4 is completed.

The extracted core specs at [docs/specs/CARD_AUTHORING_SURFACE_V1.md](docs/specs/CARD_AUTHORING_SURFACE_V1.md) and [docs/specs/FLOW_AUTHORING_SURFACE_V1.md](docs/specs/FLOW_AUTHORING_SURFACE_V1.md) are now shipped and adopted into current host authority.

## Workstream 5 - Write-capable OrketUI implementation

### Goal

Implement write behavior only after Workstream 3 and Workstream 4 close.

### Tasks

1. implement card create, save, and validate behavior only where admitted host seams exist
2. implement flow save, validate, and run behavior only where admitted host seams exist
3. keep extension-local draft state distinct from last host-confirmed state
4. update [docs/API_FRONTEND_CONTRACT.md](docs/API_FRONTEND_CONTRACT.md) and [CURRENT_AUTHORITY.md](CURRENT_AUTHORITY.md) in the same change that ships those write seams
5. fail closed on conflict, drift, or partial-save ambiguity instead of narrating false success

### Exit criteria

1. each implemented write action has live proof against the admitted host seam
2. the BFF still does not own runtime truth or hidden orchestration semantics

### Current checkpoint

Workstream 5 is completed for the bounded current slice.

The live proof path for this slice included:

1. Orket host started locally with API-key auth
2. OrketUI BFF started locally and serving the built React shell
3. host `POST /v1/cards/validate`
4. host `POST /v1/cards`
5. host `PUT /v1/cards/{card_id}`
6. host `POST /v1/flows/validate`
7. host `POST /v1/flows`
8. host `PUT /v1/flows/{flow_id}`
9. host `POST /v1/flows/{flow_id}/runs`
10. BFF `GET /`
11. BFF deep-link `GET /cards/{card_id}`
12. BFF `GET /sequencer`
13. BFF `GET /api/meta`
14. BFF `GET /api/cards`
15. BFF `GET /api/cards/{card_id}`
16. BFF `POST /api/cards/validate`
17. BFF `POST /api/flows`
18. BFF `PUT /api/flows/{flow_id}`
19. BFF `POST /api/flows/{flow_id}/runs`

Observed result for that route-level proof was `primary` / `success`.

The bounded caveat remains:

1. flow-run acceptance is live and authoritative for the current slice
2. downstream run completion still depends on the existing runtime policy and epic environment after handoff

## Workstream 6 - Cross-surface acceptance proof

### Goal

Close the lane with truthful cross-tab proof and aligned authority.

### Tasks

1. prove the required top-level tabs work together coherently
2. prove navigation across Cards, Sequencer, Board, Runs, Inspector, and Prompt Reforger
3. confirm Orket host remains agnostic to the UI shell, routes, and browser session model
4. prove the bounded write surfaces within the current cross-surface shell rather than as isolated route calls only
5. keep the Orket-side docs aligned with whatever the external repo actually ships

### Exit criteria

1. lane acceptance targets from [ORKET_EXTENSION_UI_REQUIREMENTS_V1.md](docs/projects/OrketUI/ORKET_EXTENSION_UI_REQUIREMENTS_V1.md) are met truthfully
2. the external repo is plainly the implementation authority holder
3. this repo still reflects the real boundary and does not duplicate extension implementation truth

### Current checkpoint

Workstream 6 is completed.

The live closeout proof for the bounded shipped slice covered:

1. Cards create, save, and validate through the external OrketUI shell
2. Prompt Reforger context handoff from the selected card
3. Sequencer validate, save, and bounded run initiation through the admitted flow-authoring surface
4. Board visibility for the flow-backed card after run initiation
5. Runs detail and Inspector run-context preservation through the same canonical `session_id`

Observed result for the lane closeout proof was `primary` / `success`.

## 7. Live proof rules

Every claimed implementation slice in this lane must record:

1. the observed path: `primary`, `fallback`, `degraded`, or `blocked`
2. the observed result: `success`, `failure`, `partial success`, or `environment blocker`
3. the exact host seams used
4. the exact blocker when a required seam or runtime path is unavailable

Structural proof alone is not sufficient for final implementation claims in this lane.

## 8. Planned outputs

This lane is expected to produce:

1. a live external OrketUI repo with explicit authority posture and shell/BFF scaffold
2. a read-backed OrketUI first slice
3. mockup-parity convergence for the shipped shell and tabs
4. a write-capable bounded slice on admitted host seams
5. truthful cross-surface proof for the implemented tabs
