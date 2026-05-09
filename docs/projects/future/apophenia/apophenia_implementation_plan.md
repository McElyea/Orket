# Apophenia Engine — Implementation Plan
*Revision 7 — truncation off-by-one fixed, SVG namespaced attribute handling, date authority explicit, aiofiles removed, truncation limit via HostRuntimeClient*

---

## Guiding Philosophy

Build the thing that does the thing first. Each phase ends with something real and verifiable. The weird must be observable and correctness must be provable at the end of every phase.

---

## Phase -1 — Contract Pass (1 day)
*No code written until this phase is complete.*

### Tasks

**Memory scope — confirmed**
- Smoke test `memory_write` + `memory_query` round-trip: `scope="episodic_memory"`, `session_id="apophenia.{today}"`
- **Known:** `memory_query` empty session → `{ "records": [] }`, no exception

**`memory_write` limit — confirmed through actual API path**
- Confirmed: values through 64,000 chars accepted and preserved with no truncation or rejection observed
- No host ceiling found
- `MAX_SUMMARY = 2000` is a conservative product choice, not a host limit
- Do not claim an exact ceiling

**Truncation rule — canonical form**
```python
def _trunc(value: str, max_len: int) -> str:
    if len(value) > max_len:
        return value[:max_len - 1] + "…"
    return value
```
Result is exactly `max_len` chars when truncation occurs. Applied in `ApopheniaApiClient` before every `memory_write` call and in `_write_evidence` for all string fields.
Optional evidence strings use `_optional_trunc`: empty input intentionally serializes as JSON `null`, not `""`.

**Date authority — canonical**
- Session buckets use `datetime.now().date()` in the BFF process (BFF local date)
- Browser `timestamp_utc` in payloads is metadata only — never used to derive session_id
- All session_id derivations in BFF code use one source: `datetime.now().date().isoformat()`
- Document in CONTRACT.md: session bucket = BFF local date

**BFF bind address — canonical**
- `config.bff.host`: default `"127.0.0.1"`, permitted `{"127.0.0.1", "::1"}`
- Validated before any other startup step

**Auth — confirmed**
- `GET /bootstrap/token`: loopback guard, no auth, returns persisted token
- Token persists across restarts — no rotation

**Local-first — canonical**
```toml
[local_first_override]
enabled = false
```
Orket hostname: `{"127.0.0.1", "::1"}` only. `localhost` rejected.

**SVG sanitizer — parent-tracking confirmed**
```python
parent_map = {c: p for p in root.iter() for c in p}
to_remove = []
for el in root.iter():
    # ... identify elements to remove
to_remove.append(el)
# apply after iteration:
for el in to_remove:
    if el in parent_map:
        parent_map[el].remove(el)
```
Confirm this handles nested removal correctly before Phase 3 sanitizer code is written.

**Namespaced attribute handling — confirmed approach**
- Python: attribute local name extracted as `attr.split("}")[-1] if "}" in attr else attr`
- JS: `attr.localName` used for all attribute name checks (not `attr.name`)
- Both approaches confirmed against a test SVG containing `xlink:href` before Phase 3

**Dependencies — declared**
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

**Extension dependency — pinned**
```json
{ "dependencies": { "@mozilla/readability": "0.6.0" } }
```

**Chrome alarm IDs** — in CONTRACT.md: `apophenia.daily_job`, `apophenia.retention_purge`

**Validation:** CONTRACT.md complete. Memory-write behavior through 64,000 chars recorded via actual API path with no exact host ceiling claimed. Truncation rule tested. Namespaced attr approach tested against xlink:href SVG. Date authority documented. No feature code written.

---

## Phase 0 — Foundation (1–2 days)

**Goal:** Pipes work. Bind enforced. Auth enforced. URL validated.

### Tasks

**Implementation root**
1. Verify or create `C:\Source\Orket-Extensions\Apophenia`
2. Run Phase 0 scaffolding and local commands from that root
3. Keep BFF code, Chrome extension code, config examples, packaging files, and project-local tests there
4. Keep `C:\Source\Orket` limited to planning and contract authority unless a bounded Orket host-runtime change is explicitly requested

**BFF startup sequence**
1. Load and validate config
2. Validate `config.bff.host` ∈ `{"127.0.0.1", "::1"}` — else `sys.exit(1)`
3. Validate `orket.base_url` hostname ∈ `{"127.0.0.1", "::1"}` (unless override) — else `sys.exit(1)`
4. Create output dir if missing
5. Load or generate token: read `{config_dir}/bff.token` if exists; else generate, write via `await asyncio.to_thread(token_path.write_text, token)`
6. Test Orket: `HostRuntimeClient.status()` — unreachable → `sys.exit(1)`
7. Start uvicorn: `--host config.bff.host --port config.bff.port`

**BFF middleware**
1. Loopback guard: `/bootstrap/token` + non-loopback source → 403
2. Token auth: all other routes, wrong/missing `X-Apophenia-Token` → 401
3. CORS header: `config.bff.allowed_extension_origin`

**Endpoints this phase**
- `GET /bootstrap/token` — `{ "token": loaded_token }`
- `GET /config` — nudge + memory fields
- `GET /status` — Orket health, token required
- `ApopheniaApiClient` stub: all methods raise `NotImplementedError`

**Extension**
- `manifest.json` MV3, CSP: `"extension_pages": "default-src 'none'; script-src 'self'; style-src 'unsafe-inline'; connect-src http://127.0.0.1:8090 http://[::1]:8090"`
- Worker startup: bootstrap token → store → fetch `/config` → store cap + nudge params → register alarms
- New tab: status check

**Validation (explicit)**
- `GET /status` with token → 200; without → 401
- `/bootstrap/token` non-loopback → 403
- `bff.host = "0.0.0.0"` → BFF exits before binding; TCP connect on non-loopback → connection refused
- `orket.base_url = "http://localhost:8082"` override disabled → BFF exits
- Same token value returned across two restarts
- `/config` contains `nudge` and `memory` keys

---

## Phase 1 — Content Pipeline (2–3 days)

**Goal:** Pages read, classified, stored. Truncation applied. Count gate in extension.

### Tasks

**Content extraction (content.js)** — Readability (pinned), IntersectionObserver, MutationObserver, hash dedup

**Background worker (background.js)** — cap check → POST → increment on `stored: true` → relay nudge; re-bootstrap on 401, retry once

**Boring filter (apophenia_api_client.py)** — blocklist (no LLM) → classifier (fail closed on any exception)

**Memory write with truncation (apophenia_api_client.py)**
```python
# MAX_SUMMARY = 2000 is a conservative product choice; host accepted values through 64,000 chars
# with no truncation or rejection observed. Do not claim an exact host ceiling.
# MAX_DOMAIN  = 100

async def _write_observation(self, summary, significance, register, domain, dwell_weight, timestamp):
    today = datetime.now().date().isoformat()  # BFF local date — date authority
    await self.runtime.memory_write(
        scope="episodic_memory",
        session_id=f"apophenia.{today}",
        key=f"obs.{uuid4()}",
        value=_trunc(summary, MAX_SUMMARY),
        metadata={
            "domain": _trunc(domain, MAX_DOMAIN),
            "register": register,
            "timestamp_utc": timestamp,   # metadata only, not used for bucketing
            "dwell_weight": dwell_weight,
            "significance": significance,
        }
    )
```

**Validation (explicit)**
- 10 interesting + 10 admin → exactly 10 in episodic_memory
- Mock TimeoutError → 0 writes
- Blocklist → 0 LLM calls, 0 writes
- Summary exactly MAX_SUMMARY chars → stored unchanged, no ellipsis
- Summary MAX_SUMMARY + 1 chars → stored value is exactly MAX_SUMMARY chars, ends with `…`
- Cap=3, 4 payloads → BFF receives exactly 3 requests
- Admin test: inspect all stores → empty

---

## Phase 2 — The Nudge (1–2 days)

**Goal:** You can feel it. Safe. Throttle persists.

### Tasks

**Nudge relay (background.js)** — throttle via `chrome.storage.local`, relay via `chrome.tabs.sendMessage`

**Nudge execution (content.js)**
```javascript
chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type !== "NUDGE") return;
  const el = document.activeElement;
  const tag = el ? el.tagName : "";
  if (["INPUT","TEXTAREA","SELECT"].includes(tag)) return;
  if (el && el.hasAttribute("contenteditable")) return;
  if (nudgeLock) return;
  nudgeLock = true;
  document.body.style.transition = "transform 200ms ease-out";
  document.body.style.transform = "translateY(4px)";
  setTimeout(() => {
    document.body.style.transform = "";
    setTimeout(() => { document.body.style.transition = ""; }, 210);
  }, 600);
});
```

**Validation (explicit)**
- Throttle persistence across worker restart
- Input gate: focused input + NUDGE → `transform` never set
- Style residue: after cycle, `transform === ""` and `transition === ""`
- Kill switch: `nudge.enabled = false` → all responses `nudge: false`

---

## Phase 3 — The Daily Diagram (3–4 days)

**Goal:** One real thing or nothing. Evidence always written. Schema limits enforced.

### Tasks

**`_write_evidence(...)` — async, schema-bounded, every exit point**
```python
def _optional_trunc(value: str | None, max_len: int) -> str | None:
    truncated = _trunc(value or "", max_len)
    return truncated or None


async def _write_evidence(self, date, reason, diagram_produced, **kwargs):
    observations = [
        {**o, "summary": _trunc(o["summary"], MAX_SUMMARY)}
        for o in (kwargs.get("observations") or [])
    ]
    atoms = [
        {
            "claim":   _trunc(a["claim"],   MAX_CLAIM),
            "excerpt": _trunc(a["excerpt"], MAX_EXCERPT),
        }
        for a in (kwargs.get("support_atoms") or [])
    ]
    record = {
        "date":               date,
        "reason":             reason,
        "diagram_produced":   diagram_produced,
        "observations":       observations,
        "connection_label":   _optional_trunc(kwargs.get("connection_label"), MAX_LABEL),
        "rationale":          _optional_trunc(kwargs.get("rationale"),        MAX_RATIONALE),
        "support_atoms":      atoms,
        "atom_check_failures": kwargs.get("atom_check_failures", 0),
        "verifier_result":    kwargs.get("verifier_result"),
    }
    path = self.diagram_dir / f"{date}.evidence.json"
    await asyncio.to_thread(path.write_text, json.dumps(record, indent=2))
```

**SVG generation (bff/diagram.py)**

All text through `xml.sax.saxutils.escape()` before insertion.

```python
import defusedxml.ElementTree as dET
import xml.etree.ElementTree as ET
import xml.sax.saxutils as saxutils

def _local_name(attr_key: str) -> str:
    """Extract local name from Clark notation {ns}localname or plain name."""
    return attr_key.split("}")[-1] if "}" in attr_key else attr_key

def sanitize_svg(svg_string: str) -> str | None:
    try:
        root = dET.fromstring(svg_string)
    except Exception:
        return None
    parent_map = {c: p for p in root.iter() for c in p}
    to_remove = []
    for el in root.iter():
        tag = _local_name(el.tag).lower()
        if tag in ("script", "foreignobject"):
            to_remove.append(el)
            continue
        for attr_key in list(el.attrib):
            local = _local_name(attr_key).lower()
            if local.startswith("on"):
                del el.attrib[attr_key]
            elif local == "href" and not el.attrib.get(attr_key, "").startswith("#"):
                del el.attrib[attr_key]
    for el in to_remove:
        if el in parent_map:
            parent_map[el].remove(el)
    return ET.tostring(root, encoding="unicode")
```

**Client-side sanitization (newtab.js)**
```javascript
function sanitizeSvg(svgString) {
  const parser = new DOMParser();
  const doc = parser.parseFromString(svgString, "image/svg+xml");
  const root = doc.documentElement;
  const toRemove = [];
  root.querySelectorAll("*").forEach(el => {
    const tag = el.tagName.toLowerCase();
    if (tag === "script" || tag === "foreignobject") { toRemove.push(el); return; }
    Array.from(el.attributes).forEach(attr => {
      // Use localName — not name — to strip namespace prefix before matching
      if (attr.name.startsWith("on")) el.removeAttribute(attr.name);
      if (attr.localName === "href" && !attr.value.startsWith("#")) el.removeAttribute(attr.name);
    });
  });
  toRemove.forEach(el => el.remove());
  return new XMLSerializer().serializeToString(root);
}
```

Note: `attr.name.startsWith("on")` covers both plain and prefixed on-handlers correctly because the full attribute name (including prefix) starts with `on` for all event handlers. `attr.localName === "href"` correctly catches both `href` and `xlink:href` by ignoring the prefix.

**Async file writes**
```python
# SVG
svg_path = self.diagram_dir / f"{date}.svg"
await asyncio.to_thread(svg_path.write_text, sanitized_svg)
# latest.json — only after SVG write succeeds
latest_path = self.diagram_dir / "latest.json"
await asyncio.to_thread(
    latest_path.write_text,
    json.dumps({"date": date, "file": f"{date}.svg"})
)
```

**Date in daily job**
```python
today = datetime.now().date().isoformat()  # BFF local date — single call at job start
session_id = f"apophenia.{today}"
```
`today` is computed once at the start of each job run and passed through — no secondary `date.today()` calls deeper in the stack.

**Validation (explicit)**
- Evidence written at every exit: 0, 1, 2 obs; 3 weak; 3 strong → correct reason each
- Oversized fields → all within limits in written file
- Zero-failure gate: fabricated excerpt → `deterministic_fail`, no SVG
- SVG injection (Python): `<script>` in label → absent from written SVG
- `xlink:href` (Python): SVG with `xlink:href="javascript:alert(1)"` through `sanitize_svg()` → attr absent
- SVG injection (JS): `<script>` into `sanitizeSvg()` → absent from result
- `xlink:href` (JS): SVG with `xlink:href` into `sanitizeSvg()` → attr absent
- XML escape: `<evil>` as domain → `&lt;evil&gt;` in output
- `latest.json` unchanged after failure
- Date authority: submit observation at 23:59, run job at 00:01 next day → confirm session_id matches BFF local date at job run time

---

## Phase 4 — Hardening (2–3 days)

**Goal:** Full validation suite passes. Reliable without intervention.

- SPA testing: Reddit, HN, Claude.ai, YouTube; 10,000 char extraction cap
- Network scope test: process-scoped interception on BFF PID; assert zero non-loopback TCP
- Bind test: TCP connect to non-loopback interface → connection refused
- Adversarial classifier: tune prompt
- Error handling: degraded mode, sanitizer abort, middleware catch
- Nudge style audit via Puppeteer

---

## Phase 5 — Packaging (1–2 days)

- `README.md`, `INSTALL.md`, `CONTRACT.md`
- BFF: `pip install -e .` + `uvicorn bff.server:app --host 127.0.0.1 --port 8090`
- Extension: `npm install && npm run bundle` + unpacked load
- `config.toml.example` inline-documented

---

## Technical Decisions Log

| Decision | Choice | Reason |
|----------|--------|--------|
| Truncation formula | `value[:max-1] + "…"` when `len > max` | Result is exactly `max` chars; off-by-one avoided |
| Date authority | BFF `datetime.now().date()` | BFF owns memory writes; same machine = same local date as user |
| `timestamp_utc` in payload | Metadata only, never used for session_id | Prevents date authority split |
| `today` in daily job | Computed once at job start, passed through | No secondary date calls mid-job |
| SVG attr local name (Python) | `attr.split("}")[-1] if "}" in attr else attr` | Handles Clark notation `{ns}localname` |
| SVG attr local name (JS) | `attr.localName` for href check; `attr.name` for `on*` check | `localName` strips namespace prefix; `on*` prefix check on full name is safe |
| `aiofiles` | Removed | No streaming needed; `asyncio.to_thread` is sufficient |
| File I/O in async paths | `asyncio.to_thread(path.write_text, ...)` | Prevents blocking event loop |
| Memory limit verification | Through `HostRuntimeClient.memory_write` actual path | Limit is a runtime property; local write test proves nothing |
| BFF bind address | `config.bff.host`, loopback only | Bind address is primary access control |
| Token | Persist, no rotation | Threat model doesn't justify re-bootstrap complexity |
| Daily diagram layout | Constellation | Live `/observe` records produced a supported SVG; constellation avoids Venn label-overflow risk |
| Readability dependency | `@mozilla/readability` `0.6.0` | Replaces vulnerable `0.5.0` pin while preserving the declared extraction dependency |

---

## Open Questions (remaining)

None.

---

## Milestones

| Phase | Deliverable | Est. Duration |
|-------|-------------|---------------|
| -1 | Contract, API write behavior confirmed, date authority, attr handling tested | 1 day |
| 0 | Pipes, bind, auth, URL validated, token persists | 1–2 days |
| 1 | Content stored, truncation applied and verified | 2–3 days |
| 2 | Nudge fires, safe, throttle persists | 1–2 days |
| 3 | Diagram, evidence always written, namespaced attrs handled | 3–4 days |
| 4 | Full validation suite passes | 2–3 days |
| 5 | Installable by someone else | 1–2 days |
| **Total** | | **~2.5–3 weeks** |
