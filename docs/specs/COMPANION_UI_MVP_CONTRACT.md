# Companion UI MVP Contract

Last updated: 2026-04-01
Status: Active
Owner: Orket Core

## 1. Product Intent

Companion is a real user-facing product surface.

Governing design sentence:
1. `I am here with you, not at you.`

Companion UX targets:
1. warm
2. calm
3. soft contrast
4. companion-first tone
5. emotionally available presentation

Companion must not read as:
1. clinical dashboard tooling
2. chrome-heavy telemetry UI
3. generic Tailwind SaaS shell

## 2. MVP Surface and Stack

Authoritative MVP user surface:
1. local web app

Non-MVP user surfaces:
1. CLI/TUI (developer/test harness only)

Locked UI stack:
1. React
2. Vite
3. TypeScript
4. SCSS Modules
5. Radix UI primitives
6. Lucide icons
7. plain `fetch` + thin typed API client
8. plain controlled inputs first
9. no Tailwind

## 3. Runtime Boundary Contract

Companion UI remains thin at the browser layer. Presentation and UX state live in frontend code. Product routes and product orchestration live in the Companion gateway/BFF, while generic capability execution remains host-owned behind the Orket Host API.

Companion UI must not:
1. call provider runtime internals directly
2. call the generic host runtime routes directly from frontend code
3. duplicate BFF or host orchestration, memory, or voice lifecycle logic
4. create a hidden second backend authority in frontend code

Companion BFF-owned authority:
1. outward Companion product routes under `/api/*`
2. config validation and precedence rules
3. product history shaping and chat orchestration
4. adaptive cadence logic and product-facing degradation wording

Orket/host-owned authority stays behind Host API:
1. model execution and provider dispatch
2. generic memory capability behavior
3. generic voice turn lifecycle and STT/TTS capability behavior
4. runtime/import isolation and error behavior
5. generic Host API semantics under `/v1/extensions/{extension_id}/runtime/*`

Companion UI-owned scope:
1. presentation and interaction flow
2. local UI state
3. theme and font personality selection
4. settings control surface
5. avatar/presence presentation shell

## 4. Render Resilience

No required decorative asset may block render.

If avatar/image/icon/theme assets are missing, the app must still render:
1. chat
2. settings
3. voice controls
4. memory controls
5. status

## 5. Layout Contract

Locked layout:
1. left rail: profile/settings/mode/memory/navigation
2. center: avatar/presence area
3. right: chat area
4. bottom: accordion control panel including status accordion
5. no top status bar

Avatar and chat areas must be swappable.

## 6. MVP Feature Scope

MVP UI must deliver:
1. real local Companion web experience
2. chat flow through the Companion BFF over the generic host runtime seam
3. role/style controls
4. memory controls (`clear session`, profile settings edit, memory enable/disable)
5. explicit manual silence-delay control
6. visible voice state
7. visible STT availability and text-only degradation state
8. explicit stop/submit voice controls
9. resilient rendering with graceful fallbacks
10. extensible presence structure for richer future presentation

MVP UI does not need to fully solve:
1. final avatar system
2. emotion engine
3. lip-sync
4. premium motion design
5. final art polish
6. full expressive character layer

## 7. Interaction Rules

1. Text chat is first-class and always explicit submit.
2. Voice is optional enhancement.
3. Voice timing controls must not change text submission semantics.
4. Settings/profile controls should feel integrated, not dashboard-like.
5. Status/control handling lives in bottom control panel.

## 8. Visual Contract (Light Mode)

Authoritative palette:
1. Primary Accent (Muted Teal): `#4FAF9F`
2. Secondary Accent (Sage Dust): `#C9DCD3`
3. Surface Neutral (Warm Porcelain): `#FCFAF7`
4. Emotional Highlight (Soft Coral): `#E7A59A`
5. Base Background (Warm Linen): `#F7F5F2`
6. Teal Deep: `#3F9789`
7. Primary Text (Warm Deep Charcoal): `#2E2B28`
8. Secondary Text (Warm Gray tone): `#6F6A63`
9. Soft Shadow (Warm Umber): `rgba(46, 43, 40, 0.06)`
10. Disabled/Ultra-muted tone: `#E3E7E3`

Usage rules:
1. `Teal Deep` is default focus ring and active indicator.
2. `Muted Teal` is for presence/speaking/general accenting.
3. `Soft Coral` is micro-emotion only, not general CTA emphasis.
4. `Warm Porcelain` is used for surfaces and user bubbles.
5. avoid heavy card chrome; use spacing and shape.
6. quarter-circle-edged chat bubbles are the default shape language.

## 9. Typography Contract

Companion exposes seven selectable font personalities:
1. Girly -> Quicksand
2. Manly -> IBM Plex Sans
3. Neutral -> Source Sans 3
4. Weird -> Space Grotesk
5. Elegant -> Playfair Display
6. Playful -> Nunito
7. Techno -> Fira Sans

Rules:
1. self-host fonts where practical
2. always include graceful fallback stacks
3. font load failure must never block render
4. personality changes are presentation/theme-only
5. preserve chat readability under every personality
