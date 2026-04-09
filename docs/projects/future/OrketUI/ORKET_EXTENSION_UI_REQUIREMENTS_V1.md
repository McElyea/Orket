# ORKET_EXTENSION_UI_REQUIREMENTS_V1

Last updated: 2026-04-09
Status: Draft staged future-lane product definition
Authority status: Staging only. Not current implementation authority. Read with [ORKET_EXTENSION_UI_HOST_SEAM_MAP_V1.md](docs/projects/future/OrketUI/ORKET_EXTENSION_UI_HOST_SEAM_MAP_V1.md) and [ORKET_EXTENSION_UI_OBJECT_MODEL_V1.md](docs/projects/future/OrketUI/ORKET_EXTENSION_UI_OBJECT_MODEL_V1.md).
Owner: Orket Core
Scope: UI extension requirements for a card-driven Orket extension with external BFF
Audience: extension author, UI implementer, API/BFF implementer, Orket host maintainers

## 1. Purpose

This document defines the requirements for a desktop-first UI extension that sits outside core Orket and interacts with Orket through an extension-owned BFF/API adapter layer.

The intent of this document is to lock:

1. the extension boundary,
2. the UI shell and primary surfaces,
3. the responsibilities of the extension BFF,
4. the data and state required for the UI to function,
5. the behavior of each tab,
6. the constraints required to keep Orket host agnostic to the UI.

This document is a requirements document. It does not prescribe a specific frontend framework, component library, database, deployment mechanism, or implementation sequence except where necessary to preserve authority boundaries.

## 1.1 Authority posture

This doc is future-lane product definition and staged requirements only.

It does not, by itself, authorize implementation or new host-seam invention.

This repo carries provenance for the extension lane and preserves why the work exists. The extension implementation itself remains a separate project rather than part of core Orket.

The future-lane authority packet for this extension consists of:

1. [ORKET_EXTENSION_UI_REQUIREMENTS_V1.md](docs/projects/future/OrketUI/ORKET_EXTENSION_UI_REQUIREMENTS_V1.md)
2. [ORKET_EXTENSION_UI_HOST_SEAM_MAP_V1.md](docs/projects/future/OrketUI/ORKET_EXTENSION_UI_HOST_SEAM_MAP_V1.md)
3. [ORKET_EXTENSION_UI_OBJECT_MODEL_V1.md](docs/projects/future/OrketUI/ORKET_EXTENSION_UI_OBJECT_MODEL_V1.md)

Any future implementation work for this lane must remain subordinate to [CURRENT_AUTHORITY.md](CURRENT_AUTHORITY.md), [docs/API_FRONTEND_CONTRACT.md](docs/API_FRONTEND_CONTRACT.md), and the narrower future-lane support docs [ORKET_EXTENSION_UI_HOST_SEAM_MAP_V1.md](docs/projects/future/OrketUI/ORKET_EXTENSION_UI_HOST_SEAM_MAP_V1.md) and [ORKET_EXTENSION_UI_OBJECT_MODEL_V1.md](docs/projects/future/OrketUI/ORKET_EXTENSION_UI_OBJECT_MODEL_V1.md).

If this doc conflicts with current shipped authority, current shipped authority wins.

## 1.2 Current execution blockers

The lane is not execution-ready until both of the following are true:

1. a separate extension repo exists as the implementation authority holder and carries the selected mockup artifacts, a source-of-truth note or README, and an initial shell/BFF scaffold
2. any UI action that requires host write authority maps to an already-admitted host seam or is preceded by new core spec extraction

Mockup artifacts alone are not sufficient to satisfy blocker 1.

The separate extension repo does not count as the implementation authority holder for this lane until all of the following are present together:

1. the selected mockup package
2. a source-of-truth note or README
3. an initial shell/BFF scaffold

Companion is a useful precedent for the split-repo BFF posture. It is not authority for OrketUI-specific routes, object nouns, or write semantics.

## 2. Core architectural posture

### 2.1 Boundary posture

R-001. The UI SHALL be implemented as an Orket extension, not as a core Orket host responsibility.

R-002. Core Orket SHALL remain agnostic to the existence, layout, styling, routing, and session model of the UI.

R-003. The extension SHALL own its browser-facing UI shell, web assets, session handling, view models, and UI-specific composition logic.

R-004. Core Orket SHALL continue to own runtime execution, authority decisions, emitted artifacts, run truth, and canonical identifiers.

R-005. The extension SHALL consume host-owned truth through explicit host APIs, host-emitted artifacts, or other approved extension seams rather than through direct UI-specific hooks embedded into core host behavior.

### 2.2 Companion-style BFF posture

R-006. The extension SHALL use a Companion-style BFF or thin client gateway pattern so the browser interacts with an extension-owned surface rather than directly with Orket host internals.

R-007. The extension BFF SHALL be non-authoritative. It MAY adapt, aggregate, cache, normalize, or shape data for UI consumption, but it SHALL NOT redefine runtime truth.

R-008. The extension BFF SHALL preserve stable host identifiers and source mapping so that every important UI object can be traced back to its host-owned source entity or artifact.

R-009. The extension BFF SHALL NOT introduce hidden orchestration semantics that only exist in the UI tier.

R-010. If the extension BFF performs derived summarization, projection, or aggregation, the result SHALL be recognizable as derived and SHALL remain attributable to its source records.

### 2.3 Why this is still the right plan

R-011. The Companion-style BFF pattern is the preferred architecture for this UI extension because it preserves a clean split between host runtime truth and extension-owned experience surfaces.

R-012. This remains a good plan only if the BFF stays thin in authority terms. If the BFF begins to own approval semantics, run truth, card truth, artifact truth, or hidden orchestration policy, the architecture SHALL be considered to have drifted.

## 3. Product goals

R-013. The UI SHALL support authoring cards, composing card flows, running those flows, inspecting resulting runs and artifacts, and using a dedicated Prompt Reforger surface.

R-014. The UI SHALL feel like a working authored tool, not a telemetry wall or security operations dashboard.

R-015. The UI SHALL prioritize legibility, inspectability, flow comprehension, and authored-object clarity over decorative metrics.

R-016. The UI SHALL support a desktop-first operator workflow.

R-017. The UI SHALL make relationships between cards, flows, runs, artifacts, and prompt variants understandable without requiring direct log reading for normal use.

## 4. Non-goals

R-018. The UI SHALL NOT require core Orket to know about tabs, routes, screen layouts, or design system choices.

R-019. The UI SHALL NOT be a chat-first shell.

R-020. The UI SHALL NOT be a dark terminal-style “mission control” surface.

R-021. The UI SHALL NOT rely on fictional infrastructure metrics, invented governance machinery, or decorative runtime theater.

R-022. The UI SHALL NOT treat generated prototype HTML as product truth.

## 5. Source-of-truth model

R-023. The extension SHALL distinguish between:

1. requirements truth,
2. mockup truth,
3. implementation truth.

R-024. Requirements truth SHALL be the authored requirements documents for the extension UI, including the host seam map and extension object model docs for this lane.

R-025. Mockup truth SHALL be the selected Stitch design artifacts stored by the extension project.

R-026. When those artifacts live outside core Orket, this requirements doc SHALL treat the extension project as the mockup-truth authority holder rather than implying the artifacts are checked into this repo.

R-027. Generated prototype HTML MAY be retained as exploratory material but SHALL NOT be treated as authoritative requirements or final implementation guidance.

Implementation truth remains the actual extension source code and its runtime behavior in the separate extension project.

## 6. Global shell requirements

### 6.1 Top-level surfaces

R-028. The extension SHALL provide the following top-level tabs:

1. Cards
2. Board
3. Runs
4. Inspector
5. Sequencer
6. Prompt Reforger

### 6.2 Shared shell

R-029. The extension SHALL provide a consistent desktop shell across all top-level tabs.

R-030. The shell SHALL include a top navigation surface or equivalent major-tab selector.

R-031. The shell SHALL include a collapsible left rail across the application.

R-032. The shell SHALL reserve the majority of horizontal space for the primary working surface of the active tab.

R-033. The shell MAY include a right-side inspector or detail panel when the active tab benefits from a selected-object detail view.

R-034. The shell SHALL avoid persistent multi-pane competition where secondary utilities consume the same priority as the main work surface.

### 6.3 Left rail

R-035. The left rail SHALL have two states:

1. expanded,
2. collapsed.

R-036. In expanded state, the left rail MAY show labels and contextual utilities.

R-037. In collapsed state, the left rail SHALL show icons only or an equivalently compact representation.

R-038. The collapsed rail SHALL NOT contain dense text, cramped badges, miniature tables, or other content that defeats the purpose of collapsing it.

R-039. Contextual utilities that do not need continuous visibility SHOULD live in the left rail rather than permanently occupying horizontal space.

## 7. Shared domain vocabulary

Host-owned nouns versus extension-owned projections for this lane are defined in [ORKET_EXTENSION_UI_OBJECT_MODEL_V1.md](docs/projects/future/OrketUI/ORKET_EXTENSION_UI_OBJECT_MODEL_V1.md).

R-040. The extension SHALL use a stable extension vocabulary for at least the following concepts:

1. card
2. card kind
3. display category
4. expected output type
5. prompt
6. input
7. output
8. flow
9. node
10. edge
11. run
12. epic
13. phase
14. artifact
15. graph
16. selected item
17. prompt variant
18. evaluation result

R-041. The extension SHALL distinguish between card kind, expected output type, and display category.

R-042. Visual category cues MAY be used for readability, but display category SHALL NOT be the only semantic description of a card.

## 8. Shared data and state requirements

### 8.1 Shared selection model

R-043. The extension SHALL implement a shared selection model that can represent at least:

1. selected card,
2. selected flow,
3. selected node,
4. selected run,
5. selected artifact,
6. selected graph node,
7. selected prompt candidate.

R-044. Cross-surface navigation SHALL preserve sufficient selection context for Inspector, Board, Runs, Sequencer, and Prompt Reforger to interoperate coherently.

### 8.2 Shared UI states

R-045. Every major surface SHALL define and handle the following states where applicable:

1. empty,
2. loading,
3. partial,
4. invalid,
5. running,
6. success,
7. failed.

R-046. Empty states SHALL explain what object is missing and what the user can do next.

R-047. Loading states SHALL avoid large unexplained blank regions.

R-048. Error states SHALL identify which operation or data load failed.

### 8.3 Shared navigation

R-049. The extension SHALL support predictable movement between the following relationships where applicable:

1. Cards to Sequencer,
2. Sequencer to Board,
3. Board to Runs,
4. Runs to Inspector,
5. Inspector to related artifacts or runs,
6. Prompt Reforger to the relevant card or prompt context.

## 9. Visual system requirements

R-050. The extension SHALL use a light theme.

R-051. The extension SHALL use a warm cream or parchment base and emerald as the primary accent family.

R-052. The extension SHALL maintain a calm, premium, authored-tool aesthetic.

R-053. Brand accent colors SHALL remain distinct from semantic success, warning, and error colors.

R-054. The extension SHALL avoid the dark black-and-blue mission-control styling used by earlier exploratory designs.

R-055. The extension SHALL prefer readable structure, spacing, and hierarchy over ornament.

## 10. BFF requirements

Allowed host-facing seams for the extension BFF are defined in [ORKET_EXTENSION_UI_HOST_SEAM_MAP_V1.md](docs/projects/future/OrketUI/ORKET_EXTENSION_UI_HOST_SEAM_MAP_V1.md).

### 10.1 Boundary and authority

R-056. The extension BFF SHALL be the browser-facing entry point for the UI.

R-057. The extension BFF SHALL isolate browser concerns, session concerns, UI-friendly shaping, and extension-local composition from Orket host.

R-058. The extension BFF SHALL NOT cause Orket host to adopt UI-specific routes or UI-only data contracts.

R-059. The extension BFF SHALL preserve host identifiers in its responses wherever a UI object maps to a host-owned entity.

R-060. The extension BFF SHALL identify derived or synthesized response fields when it creates them.

### 10.2 Data shaping

R-061. The BFF MAY aggregate data from multiple host surfaces to support a coherent screen.

R-062. The BFF MAY translate host payloads into stable UI-facing read models.

R-063. The BFF SHOULD prefer explicit read models over leaking raw backend payloads directly into page components.

R-064. The BFF SHALL maintain a stable mapping from UI-facing read models back to host-owned source entities and artifacts.

### 10.3 Security and session posture

R-065. Browser credentials, sessions, or browser-safe tokens SHALL terminate at the extension BFF rather than at core host-facing internal interfaces.

R-066. The BFF SHALL prevent accidental exposure of internal host credentials, extension secrets, or privileged host-only tokens to the browser.

## 11. Tab requirements

## 11.1 Cards tab

### Purpose

R-067. The Cards tab SHALL be the first-class authoring surface for a single card.

### Primary user questions

R-068. The Cards tab SHALL let the user answer:

1. what this card does,
2. what category it belongs to,
3. what prompt drives it,
4. what inputs it expects,
5. what outputs it should produce,
6. whether the card is valid enough to use.

### Main objects shown

R-069. The Cards tab SHALL work primarily with:

1. card,
2. prompt,
3. inputs,
4. outputs,
5. expected output type,
6. display category,
7. validation result.

### Layout

R-070. The Cards tab SHALL provide:

1. a card list or card library region,
2. a primary card editor region,
3. a summary, validation, or relationships region.

### Required data

R-071. The Cards tab SHALL support at least the following fields:

1. card name,
2. card description or purpose,
3. card kind,
4. expected output type,
5. display category,
6. prompt,
7. inputs,
8. expected outputs,
9. notes or constraints,
10. approval expectation,
11. artifact expectation.

### Actions

R-072. The Cards tab SHALL support at least:

1. create card,
2. select card,
3. edit card,
4. duplicate card,
5. save card,
6. validate card.

### State handling

R-073. The Cards tab SHALL support no-card, loading, unsaved, invalid, save-success, and save-failure states.

### Constraints

R-074. The prompt SHALL remain visible and editable as a first-class field.

R-075. The Cards tab SHALL NOT hide the prompt behind an “advanced” drawer by default.

R-076. The Cards tab SHALL NOT collapse card semantics into generic workflow-node language.

### Success condition

R-077. The Cards tab is successful when a user can create or edit a complete, understandable, reusable card.

## 11.2 Board tab

### Purpose

R-078. The Board tab SHALL be the operating surface for live flow state and epic progress.

### Primary user questions

R-079. The Board tab SHALL let the user answer:

1. what is happening now,
2. which card is currently running,
3. what phase the flow is in,
4. what came before,
5. what comes next,
6. what artifacts already exist for the epic.

### Main objects shown

R-080. The Board tab SHALL work primarily with:

1. epic,
2. phase columns,
3. cards on the board,
4. current card,
5. previous card,
6. next card,
7. recent epic artifacts.

### Layout

R-081. The Board tab SHALL provide:

1. a main kanban or phase board surface,
2. a contextual active-run drawer or side panel,
3. a top context summary area where useful.

### Required data

R-082. The Board tab SHALL support at least:

1. epic identity,
2. board phases or columns,
3. cards per phase,
4. current active card if any,
5. previous and next card where meaningful,
6. recent artifacts for the active epic,
7. current run status.

### Actions

R-083. The Board tab SHALL support at least:

1. selecting a card,
2. opening the active run context,
3. opening related artifacts,
4. moving to the corresponding run or inspector surface.

### State handling

R-084. The Board tab SHALL define behavior for:

1. no active epic,
2. no active run,
3. active run,
4. paused or failed run,
5. board loading.

### Constraints

R-085. The Board tab SHALL prioritize flow state over telemetry theater.

R-086. The Board tab SHALL NOT center its design around latency bars, integrity bars, or decorative monitoring widgets.

### Success condition

R-087. The Board tab is successful when a user can understand current orchestration flow at a glance.

## 11.3 Runs tab

### Purpose

R-088. The Runs tab SHALL be the browse surface for current and past runs.

### Primary user questions

R-089. The Runs tab SHALL let the user answer:

1. what runs exist,
2. which are active,
3. which have failed,
4. which epic or flow they belong to,
5. which run to inspect next.

### Main objects shown

R-090. The Runs tab SHALL work primarily with:

1. run,
2. epic,
3. flow,
4. phase,
5. status,
6. artifact count.

### Layout

R-091. The Runs tab SHALL provide:

1. search and filter controls,
2. a primary runs table,
3. an optional preview region if it does not crowd the table.

### Required data

R-092. The Runs tab SHALL support at least:

1. run id,
2. epic,
3. flow,
4. start time,
5. end time,
6. current or final card,
7. phase,
8. status,
9. artifact count.

### Actions

R-093. The Runs tab SHALL support at least:

1. filtering,
2. searching,
3. selecting a run,
4. opening a run in Inspector.

### Constraints

R-094. The Runs tab SHALL remain practical and table-driven.

R-095. The Runs tab SHALL NOT become a decorative KPI dashboard.

### Success condition

R-096. The Runs tab is successful when a user can find and open the correct run quickly.

## 11.4 Inspector tab

### Purpose

R-097. The Inspector tab SHALL be the browse-and-inspect surface for artifacts, raw data, and graphs.

### Primary user questions

R-098. The Inspector tab SHALL let the user answer:

1. what artifacts exist,
2. what this selected item contains,
3. what relationships it has,
4. what run or graph context it belongs to,
5. what metadata is associated with it.

### Main objects shown

R-099. The Inspector tab SHALL work primarily with:

1. artifact tree,
2. file or object content,
3. graph,
4. selected node,
5. metadata,
6. related artifacts,
7. related run context.

### Layout

R-100. The Inspector tab SHALL provide:

1. a browse region for artifacts and graphs,
2. a main viewer region,
3. a right-side metadata or selected-item inspector region.

### Required data

R-101. The Inspector tab SHALL support at least:

1. artifact lists or trees,
2. file metadata,
3. renderable text or JSON content,
4. image content where applicable,
5. graph structures,
6. selected item metadata,
7. associated run references.

### Actions

R-102. The Inspector tab SHALL support at least:

1. browsing artifacts,
2. opening artifacts,
3. selecting graph nodes,
4. changing view modes,
5. opening related items.

### Graph interaction

R-103. Graph content SHALL support selectable nodes or an equivalent interaction that lets the user inspect specific graph entities.

R-104. Selecting a graph node SHALL update the right-side inspector with node-specific detail.

### Constraints

R-105. The Inspector tab SHALL emphasize inspection rather than operational theater.

R-106. The Inspector tab SHALL NOT center its language around mystical system behavior, fictional infrastructure, or invented provenance drama.

### Success condition

R-107. The Inspector tab is successful when a user can inspect the selected object and understand its context.

## 11.5 Sequencer tab

### Purpose

R-108. The Sequencer tab SHALL be the visual authoring environment for multi-card flows.

### Primary user questions

R-109. The Sequencer tab SHALL let the user answer:

1. what cards are in this flow,
2. how they connect,
3. where the flow starts,
4. where it branches,
5. where it merges,
6. whether the flow is valid enough to run.

### Main objects shown

R-110. The Sequencer tab SHALL work primarily with:

1. flow,
2. nodes,
3. edges,
4. assigned cards,
5. branch nodes,
6. merge nodes,
7. selected node details.

### Layout

R-111. The Sequencer tab SHALL use a three-zone layout:

1. collapsible left utility rail,
2. main composition canvas,
3. right inspector panel.

### Left rail

R-112. The Sequencer left rail SHALL hold:

1. flow status,
2. run history,
3. component palette.

R-113. The left rail SHALL behave as a utility rail rather than as a full equal-priority workspace.

### Canvas

R-114. The composition canvas SHALL receive the largest share of horizontal space.

R-115. The canvas SHALL make start, card nodes, branches, merges, and final state readable at a glance.

### Right inspector

R-116. The right inspector SHALL present at least:

1. assigned card,
2. category,
3. expected output,
4. prompt summary,
5. incoming edges,
6. outgoing edges,
7. notes,
8. validation state.

### Required node concepts

R-117. The Sequencer SHALL support at least:

1. Start,
2. Requirement Card,
3. Code Card,
4. Critique Card,
5. Approval Card,
6. Branch,
7. Merge,
8. Final.

### Actions

R-118. The Sequencer SHALL support at least:

1. add node,
2. connect nodes,
3. assign card,
4. edit node,
5. delete node,
6. validate flow,
7. save flow,
8. run flow.

### Constraints

R-119. The Sequencer SHALL NOT use generic workflow-builder jargon such as processor, gateway, logic node, or deploy-flow language as its primary semantics.

R-120. The Sequencer SHALL NOT allow primary controls to be cut off or permanently cramped.

### Success condition

R-121. The Sequencer is successful when a user can compose and validate a readable flow without spatial competition overwhelming the canvas.

## 11.6 Prompt Reforger tab

### Purpose

R-122. The Prompt Reforger tab SHALL be the specialized workflow for adapting prompts, comparing variants, and evaluating candidate results.

### Primary user questions

R-123. The Prompt Reforger tab SHALL let the user answer:

1. what the source prompt is,
2. what candidate variants exist,
3. how they differ,
4. which result is acceptable,
5. what the evaluation outcome is.

### Main objects shown

R-124. The Prompt Reforger tab SHALL work primarily with:

1. source prompt,
2. candidate variants,
3. diff or comparison views,
4. evaluation results,
5. result states.

### Layout

R-125. The Prompt Reforger tab SHALL provide:

1. source prompt region,
2. candidate comparison region,
3. evaluation result region.

### Required result states

R-126. The Prompt Reforger tab SHALL support at least:

1. certified,
2. certified_with_limits,
3. unsupported.

### Actions

R-127. The Prompt Reforger tab SHALL support at least:

1. generating or selecting variants,
2. comparing variants,
3. inspecting result details,
4. selecting a preferred result where supported.

### Constraints

R-128. The Prompt Reforger tab SHALL feel analytical and tool-like.

R-129. The Prompt Reforger tab SHALL NOT read as a marketing-style benchmark page or decorative KPI board.

### Success condition

R-130. The Prompt Reforger tab is successful when a user can compare variants and understand the acceptability of the result.

## 12. Cross-tab requirements

R-131. Cards SHALL feed Sequencer through card assignment and card selection workflows.

R-132. Sequencer SHALL feed Board and Runs through saved or initiated flows.

R-133. Runs SHALL open cleanly into Inspector.

R-134. Inspector SHALL preserve links back to the originating run or artifact context.

R-135. Prompt Reforger SHOULD be able to open in the context of a selected card prompt or a prompt-focused workflow when such a relationship exists.

## 13. Mockup artifact guidance

R-136. The extension project SHALL retain selected Stitch mockups as visual reference material.

R-137. Mockup artifacts MAY be stored under any equivalent project-relative path, including a structure such as `stitch-design/<tab>/screen.png` and `stitch-design/<tab>/code.html`.

R-138. The project SHALL document that `screen.png` is the primary visual reference and `code.html` is helper material rather than product truth.

In the current split-repo setup, those mockup artifacts may live in the external OrketUI extension repo rather than in core Orket.

This repo may still retain the staged requirements and rationale for those artifacts so Orket-side provenance stays explicit.

## 14. First-slice implementation targets

R-139. The first implementation slice SHALL preserve the extension boundary and Companion-style BFF posture even if some tabs begin with mocked or incomplete data.

R-140. The first implementation slice SHOULD prioritize:

1. shell,
2. Cards,
3. Sequencer,
4. Board,
5. Runs,
6. Inspector,
7. Prompt Reforger.

R-141. Early implementation MAY use placeholder data, but placeholder data SHALL use extension vocabulary rather than generic workflow-builder or infrastructure-theater terminology.

UI actions named in this doc as product requirements, including `create card`, `save card`, `validate card`, `save flow`, and `run flow`, remain staged product intent only unless they map to admitted host seams or new core specs are extracted first.

## 15. Future acceptance targets

These are future-lane product acceptance targets, not current execution-proof gates.

R-142. The UI extension is acceptable only if core Orket remains agnostic to the UI’s routes, tabs, visual design, and browser session model.

R-143. The UI extension is acceptable only if the extension BFF remains non-authoritative with respect to host runtime truth.

R-144. The UI extension is acceptable only if a user can:

1. author cards,
2. compose flows,
3. view active flow state,
4. browse runs,
5. inspect artifacts and graphs,
6. use Prompt Reforger,
7. navigate across these surfaces coherently.

R-145. The UI extension is acceptable only if the implemented product still reads as an authored cream-and-emerald work surface rather than as a mission-control dashboard.

## 16. Final architectural answer

Yes: using the same style BFF posture as Companion remains the correct plan.

It preserves the right seam:

1. host owns runtime truth,
2. extension owns experience,
3. BFF owns browser-facing adaptation,
4. the browser never becomes the contract-defining surface,
5. Orket host remains reusable and UI-agnostic.

The plan stops being correct only if the BFF or frontend begins to silently own orchestration truth, approval truth, or host policy semantics.
