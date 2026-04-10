# Contract Delta: OrketUI Write Surfaces 2026-04-09

## Summary
- Change title: Ship host write surfaces for card and flow authoring
- Owner: Orket Core
- Date: 2026-04-09
- Affected contract(s): [docs/specs/CARD_AUTHORING_SURFACE_V1.md](docs/specs/CARD_AUTHORING_SURFACE_V1.md), [docs/specs/FLOW_AUTHORING_SURFACE_V1.md](docs/specs/FLOW_AUTHORING_SURFACE_V1.md), [docs/API_FRONTEND_CONTRACT.md](docs/API_FRONTEND_CONTRACT.md), [CURRENT_AUTHORITY.md](CURRENT_AUTHORITY.md), [docs/projects/OrketUI/ORKET_EXTENSION_UI_WRITE_SEAM_INVENTORY_V1.md](docs/projects/OrketUI/ORKET_EXTENSION_UI_WRITE_SEAM_INVENTORY_V1.md)

## Delta
- Prior behavior: OrketUI had a truthful read-backed first slice, while the card and flow authoring seams were still documented as future or draft host work.
- New behavior: Orket now ships admitted card authoring routes, admitted flow authoring routes, current authority adoption for those routes, a bounded authored-card runtime projection at `config/epics/orket_ui_authored_cards.json`, and a bounded admitted `run flow` slice that returns authoritative acceptance through `session_id`.
- Why this change was required: the OrketUI lane had already crossed from planning into live mockup-parity and BFF implementation, so leaving the write surfaces in draft-only language would have created authority drift.

## Migration Plan
1. Compatibility window: the bounded routes are now mounted and authoritative.
2. Migration steps:
   - keep the host and BFF on the admitted route families documented here
   - keep authored issue-card composition on the bounded runtime projection path rather than inventing a second run-card authority
   - keep OrketUI write claims within the bounded current slice
   - expand flow-run semantics only through a later explicit contract delta
3. Validation gates:
   - live host route proof for create, save, validate card; create, save, validate flow; and bounded flow-run acceptance
   - `python scripts/governance/check_docs_project_hygiene.py`
   - `git diff --check`

## Rollback Plan
1. Rollback trigger: the shipped route or bounded run slice proves incompatible with the intended host authority boundary or produces unacceptable drift from live runtime behavior.
2. Rollback steps:
   - revert the mounted route family and matching authority updates together
   - revert the linked OrketUI inventory and roadmap updates
   - return the lane to read-backed behavior only until a corrected host slice ships
3. Data/state recovery notes: persisted card authoring metadata remains on the host card surface, and persisted flow definitions remain in `.orket/durable/db/orket_ui_flows.sqlite3`; rollback must preserve or migrate that truth explicitly rather than silently discarding it.

## Versioning Decision
- Version bump type: shipped bounded contract surface
- Effective version/date: 2026-04-09
- Downstream impact: OrketUI may now truthfully use the shipped card and flow authoring routes for the bounded admitted slice, including bounded flow-run composition with newly authored issue cards, while broader flow-execution semantics remain out of scope until a later contract expansion.
