# Apophenia Engine — Product Requirements
*Revision 7 — truncation off-by-one fixed, SVG namespaced attribute handling, date authority defined, aiofiles removed, truncation limit via actual API path*

---

## Vision

A browser extension that watches you browse, says nothing, and once a day surfaces one genuine connection between three things you encountered — presented without commentary. The uncanny feeling comes not from fiction but from the fact that the connection is model-supported by evidence drawn directly from the day's observations. The system is a presence, not a tool. It must never break immersion.

---

## Core Principles

1. **Invisible by default.** No settings screens, no popups, no badges, no onboarding flows.
2. **Purely passive.** Significance is inferred entirely from behavioral signals. The user does nothing.
3. **Local first.** All content, memory, and inference runs on the user's machine. BFF binds to loopback only. No intentional off-device calls from the BFF process.
4. **Architecturally agnostic.** Orket is a generic host runtime. All Apophenia logic lives in the BFF layer.
5. **The weird must be load-bearing.** Connections must be model-supported by evidence atoms drawn from actual observations, with zero fabricated citations.
6. **Fail closed on ambiguity.** Classification failure, LLM timeout, or any failed evidence check produces no SVG, no `latest.json` update, and no additional memory write. Evidence records are always written. Observations already stored before the daily job ran are not affected.

---

## Architecture

```
Chrome Extension (content scripts + nudge executor + new tab surface)
        ↓  localhost HTTP + shared secret header
Apophenia FastAPI BFF  (binds to 127.0.0.1 only, port 8090)
        ↓
ApopheniaApiClient  (wraps HostRuntimeClient)
        ↓
HostRuntimeClient  (unchanged from companion_extension)
        ↓
Orket generic endpoints  (llm/generate, memory/write, memory/query)
        ↓
Local LLM via Ollama
```

---

## Implementation Location

- Implementation root: `C:\Source\Orket-Extensions\Apophenia`
- All Apophenia BFF code, Chrome extension code, local config examples, packaging files, and project-local tests live under this root.
- `C:\Source\Orket` keeps planning and contract authority only, unless a bounded Orket host-runtime change is explicitly requested.

---

## BFF Bind Address

- Config field: `config.bff.host`, default `"127.0.0.1"`, permitted: `{"127.0.0.1", "::1"}` only
- Any other value at startup → `sys.exit(1)`: "bff.host must be 127.0.0.1 or ::1."
- Uvicorn launched as: `uvicorn bff.server:app --host {config.bff.host} --port {config.bff.port}`
- Loopback guard on `/bootstrap/token` remains as defense-in-depth; bind address is primary control

---

## Local Authentication

**Bootstrap endpoint:** `GET /bootstrap/token`
- Loopback guard (defense-in-depth): non-`{"127.0.0.1", "::1"}` source → 403
- Returns `{ "token": "<value>" }`

**Token lifecycle:** generated once with `secrets.token_urlsafe(32)`, persisted to `{config_dir}/bff.token`. Read on subsequent startups — no rotation. Replaced only by manual deletion.

**Threat model:** token blocks accidental cross-process calls. Same-user process can obtain token via bootstrap. Bind address prevents off-machine access.

**All protected routes:** `X-Apophenia-Token` required. Missing or wrong → 401.

---

## Local-First Enforcement

```toml
[local_first_override]
enabled = false
```
Orket hostname must be in `{"127.0.0.1", "::1"}`. `localhost` rejected — DNS-resolved, inconsistent.

---

## Date Authority

**Session buckets use BFF local date.**

- `session_id` format: `apophenia.{YYYY-MM-DD}` where the date is `datetime.now().date()` in the BFF process
- Browser payloads include `timestamp_utc` as metadata for record-keeping only — it is never used to derive the session bucket
- Since BFF and browser run on the same machine in local-first mode, BFF local date equals user's local date
- All BFF code that derives a session_id must use the same `datetime.now().date()` call — no UTC, no browser-reported date

---

## Memory Scope

```
scope:      episodic_memory
session_id: apophenia.{YYYY-MM-DD}   # BFF local date
key:        obs.{uuid4}
```

**Known behavior:** `memory_query` for a session_id with no entries returns `{ "records": [] }` — no exception.

---

## Memory Write Truncation Rule

All truncation produces strings of length exactly `MAX` chars when truncation occurs. The ellipsis character `…` (1 char) replaces the last character of the truncated value, so total length never exceeds `MAX`.

```
truncated = value[:MAX - 1] + "…"  if len(value) > MAX  else value
```

`HostRuntimeClient.memory_write` accepted and preserved values through 64,000 chars with no truncation or rejection observed. `MAX_SUMMARY = 2000` is a conservative product choice, not a host limit; do not claim an exact host ceiling.

| Field | Product MAX | Applied in |
|-------|-------------|------------|
| `memory_write` value (summary) | 2,000 | `ApopheniaApiClient._write_observation` |
| Evidence `observations[].summary` | 2,000 | `_write_evidence` |
| Evidence `support_atoms[].excerpt` | 200 | `_write_evidence` |
| Evidence `support_atoms[].claim` | 200 | `_write_evidence` |
| Evidence `rationale` | 1,000 | `_write_evidence` |
| Evidence `connection_label` | 50 | `_write_evidence` |
| `metadata.domain` | 100 | `ApopheniaApiClient._write_observation` |

---

## Content Acquisition

### What is tracked
- Readable text of pages visited, scroll-weighted by dwell time
- Specific content on SPAs via MutationObserver
- High-dwell blocks ranked higher in summary

### What is never tracked
- Life administration: medical, pharmacy, insurance, government, HR/payroll
- Work: domain blocklist + content classifier
- Classifier failure → fail closed
- Content reaching Stage 2 classifier may exist in Orket's internal logs

### Content extraction
- Mozilla Readability; fallback to `innerText` + selector strip
- 10 vertical bands via IntersectionObserver
- MutationObserver with 2s debounce, hash dedup for SPAs

---

## The Boring Filter

**Stage 1 — Domain blocklist:** instant drop, no LLM call.

**Stage 2 — Content classifier** (`llm/generate`): must return `interesting` or `administrative`. Any failure → fail closed.

---

## Privacy Posture

| Artifact | Location | Content | Retention |
|----------|----------|---------|-----------|
| Observations | Orket `episodic_memory` | Truncated summaries, metadata | 7 days |
| Daily SVG | User output dir | Domain label + 6-word excerpt, connection label | Indefinite |
| Evidence record | User output dir | Derived, schema-bounded (see limits table) | Indefinite |
| BFF token | `{config_dir}/bff.token` | Random token | Persisted |
| BFF logs | Stderr only | No content logged | Session only |
| LLM prompt logs | Orket internal | Orket's retention policy | Outside Apophenia's control |
| Extension state | `chrome.storage.local` | Config values, counters, timestamps | Cleared on uninstall |
| Blocklisted content | Never written | — | — |

**Scoped guarantee:** Apophenia output files and BFF logs contain no raw browsing content. All stored content is LLM-derived and length-bounded by the limits table. Content reaching Stage 2 may exist in Orket's internal logs.

---

## Observation Count Ownership

- Extension increments `chrome.storage.local["obs.count.{YYYY-MM-DD}"]` after `stored: true`
- Extension enforces cap as pre-filter gate; cap from `GET /config`
- Daily job uses `memory_query` result length as authoritative count

---

## Connection Verification

Connections are **model-supported by evidence atoms**, not independently verified facts. The deterministic check proves cited excerpts exist in source material.

### Verification gate — zero atom failures required
1. LLM pass 1: return `{ label, rationale, support_atoms: [{ claim, excerpt }] }`
2. Deterministic check: every `atom.excerpt.lower()` must be a substring of its observation summary. Any failure → reject.
3. LLM pass 2 (verifier): `supported | weak | rejected`
4. `weak` or `rejected` → no SVG, no `latest.json` update
5. `supported` + zero failures → produce SVG

### Evidence record — always written, schema-bounded

Evidence records are audit files, not user-facing output. Written at every exit point regardless of outcome.

```json
{
  "date": "2026-05-06",
  "reason": "supported | weak | rejected | deterministic_fail | insufficient_observations | no_observations | sanitizer_error",
  "diagram_produced": false,
  "observations": [
    { "domain": "≤100 chars", "summary": "≤2000 chars", "dwell_weight": 0.8, "register": "≤20 chars" }
  ],
  "connection_label": "≤50 chars",
  "rationale": "≤1000 chars",
  "support_atoms": [
    { "claim": "≤200 chars", "excerpt": "≤200 chars" }
  ],
  "atom_check_failures": 0,
  "verifier_result": null
}
```

---

## The Presence — Nudge System

- Body translate only: 4px, 200ms ease-out, returns within 600ms. No zoom.
- Input gate: abort if `document.activeElement` is INPUT, TEXTAREA, SELECT, or contenteditable
- Global throttle: `chrome.storage.local`, persists across worker restarts
- Hard kill switch: `config.nudge.enabled = false` → BFF returns `nudge: false` always
- Per-page lock: content script memory. Max one nudge per page per load.
- BFF `/observe` response owns nudge decision — extension does not decide independently

---

## The Daily Diagram

Once per day, one SVG or nothing. Evidence record always written.

### Output files
- `{diagram_dir}/{YYYY-MM-DD}.svg` — written only on success
- `{diagram_dir}/{YYYY-MM-DD}.evidence.json` — always written
- `{diagram_dir}/latest.json` — updated only on successful SVG write

### SVG rendering safety

**Server side (Python):**
- All text values through `xml.sax.saxutils.escape()` before SVG string construction
- Sanitize with `defusedxml` after construction using parent-map approach (confirmed in Phase -1)
- **Namespaced attribute handling:** attribute local name is authority. In Python's ElementTree, namespaced attributes appear as `{namespace-uri}localname`. Extract local name as `attr.split("}")[-1] if "}" in attr else attr` before matching against `"href"` or `on*` prefix check.
- Failure or unexpected removal → abort, write evidence record `reason: sanitizer_error`, no SVG

**Client side (JS):**
- `DOMParser` + `XMLSerializer` whitelist walk
- **Namespaced attribute handling:** use `attr.localName` (not `attr.name`) when checking for `"href"` and `on*` prefix — `attr.localName` returns the unprefixed local name regardless of namespace
- Remove `script`, `foreignObject`; remove attrs where `attr.name.startsWith("on")` or `attr.localName === "href"` with non-`#` value
- Extension CSP: `default-src 'none'; script-src 'self'; style-src 'unsafe-inline'; connect-src http://127.0.0.1:8090 http://[::1]:8090`

---

## Chrome Extension Architecture (MV3)

| State | Storage |
|-------|---------|
| Nudge throttle timestamp | `chrome.storage.local` |
| Daily job fired flag | `chrome.storage.local` |
| Observation pre-filter count | `chrome.storage.local` |
| BFF auth token | `chrome.storage.local` |
| Daily job + retention schedules | `chrome.alarms` |
| Per-page nudge lock | Content script memory |

---

## BFF API Contract

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/bootstrap/token` | None (loopback guard) | Return persistent auth token |
| GET | `/config` | Yes | Nudge params + memory cap |
| POST | `/observe` | Yes | Classify, store, return nudge instruction |
| GET | `/diagram/today` | Yes | Return today's SVG or 404 |
| POST | `/diagram/generate` | Yes | Trigger daily job (idempotent) |
| GET | `/status` | Yes | Health, observation count, job state |

---

## Dependencies

### BFF
```toml
# pyproject.toml [project.dependencies]
fastapi>=0.110
uvicorn>=0.29
defusedxml>=0.7.1
pydantic>=2.0
toml>=0.10
```
No `aiofiles` — `asyncio.to_thread` is the file I/O pattern.
The external implementation root owns its own dependency authority. Do not add Apophenia dependencies to Orket's `pyproject.toml` unless Apophenia code is explicitly implemented inside the Orket repo.

### Extension
```json
{ "dependencies": { "@mozilla/readability": "0.6.0" } }
```

---

## Configuration

```toml
[output]
diagram_dir = "C:/source/DailyDiagram"

[orket]
base_url = "http://127.0.0.1:8082"
extension_id = "orket.apophenia"
api_key = ""

[bff]
host = "127.0.0.1"
port = 8090
allowed_extension_origin = "chrome-extension://YOUR_EXTENSION_ID"

[filter]
domain_blocklist = ["mychart.com", "paylocity.com"]

[schedule]
min_browse_hours = 6
fixed_local_time = "23:00"
rollover_behavior = "next_open"

[nudge]
enabled = true
min_interval_seconds = 300
significance_threshold = 0.6

[memory]
retention_days = 7
max_observations_per_day = 50

[local_first_override]
enabled = false
```

---

## Non-Requirements

- No user accounts, no sync, no cloud
- No settings UI, no notifications, no explicit feedback mechanism
- No explanation of connections, no history browser, no mobile support
- No zoom-based nudge

---

## Validation Requirements

| Requirement | Explicit Check |
|-------------|----------------|
| BFF binds loopback only | TCP connect to BFF on non-loopback interface; assert connection refused |
| Non-loopback `bff.host` rejected | `bff.host = "0.0.0.0"` → assert BFF exits before binding |
| Boring filter drops admin | 20 fixtures; assert 0 admin entries in episodic_memory |
| LLM timeout fails closed | Mock TimeoutError; assert stored count unchanged |
| Filtered content not in Apophenia stores | POST admin; inspect all stores; assert empty |
| BFF auth enforced | No token on protected route; assert 401 |
| Bootstrap loopback guard | Non-loopback source; assert 403 |
| Token persists across restart | Record token, restart, bootstrap; assert same value |
| Orket URL validated | Non-loopback + override disabled; assert BFF exits |
| `localhost` rejected | `orket.base_url = http://localhost:8082` + override disabled; assert exit |
| Date authority | Submit observation near midnight; assert session_id uses BFF local date |
| Truncation off-by-one | Input exactly MAX chars → no truncation; MAX+1 chars → result is exactly MAX chars |
| Truncation limit via API | Write value at boundary through `HostRuntimeClient.memory_write`; confirm round-trip; confirm behavior above limit |
| Evidence schema limits | Oversized fields submitted; assert all within limits in written file |
| Nudge throttle persists | Fire, kill worker, restart, high-significance observe; assert blocked |
| Input safety gate | Focused input + NUDGE; assert `transform` never set |
| Evidence always written | 0, 1, 2 obs; 3 weak; 3 strong → correct reason each case |
| Zero atom failures required | Fabricated excerpt → `deterministic_fail`, no SVG |
| SVG namespaced attr (Python) | SVG with `xlink:href="javascript:alert(1)"` → assert attr absent from sanitized output |
| SVG namespaced attr (JS) | SVG with `xlink:href` passed to `sanitizeSvg()` → assert attr absent from result |
| SVG injection blocked | `<script>` in label; assert absent from output |
| XML escaping | `<evil>` as domain; assert `&lt;evil&gt;` in SVG |
| `latest.json` not updated on failure | Weak connection → assert latest.json unchanged |
| BFF makes no off-device calls | Process-scoped network interception on BFF PID; assert zero non-loopback TCP |
| Observation cap gate | Cap=3, 4 payloads; assert 4th never reaches BFF |
| defusedxml in dependency authority | Assert external project manifest contains `defusedxml` before first import; if explicitly implemented inside Orket, assert Orket `pyproject.toml` updates in the same commit |
