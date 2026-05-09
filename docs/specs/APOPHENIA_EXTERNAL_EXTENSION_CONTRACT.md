# Apophenia External Extension Contract

Last updated: 2026-05-09
Status: Active durable contract for the external Apophenia extension. Phase 0-3 implementation and proof gates passed on 2026-05-08.

## Authority

This contract is the durable execution contract for Apophenia.

Archived source documents:
1. `docs/projects/archive/apophenia/2026-05-09-CLOSEOUT/apophenia_requirements.md`
2. `docs/projects/archive/apophenia/2026-05-09-CLOSEOUT/apophenia_implementation_plan.md`
3. `docs/projects/archive/apophenia/2026-05-09-CLOSEOUT/CLOSEOUT.md`

Orket remains a generic host runtime. Apophenia-specific behavior lives in the BFF layer and Chrome extension. Do not add Apophenia-specific semantics to Orket core runtime paths.

## Implementation Root

Implementation root: `C:\Source\Orket-Extensions\Apophenia`

All Phase 0+ BFF code, Chrome extension code, local config examples, packaging files, and project-local tests live under the implementation root above.

`C:\Source\Orket` keeps Apophenia contract authority only, unless the user explicitly requests a bounded Orket host-runtime change.

## Architecture Boundary

```text
Chrome Extension
  -> Apophenia FastAPI BFF
  -> ApopheniaApiClient
  -> HostRuntimeClient
  -> Orket generic extension runtime endpoints
  -> Local LLM provider
```

`HostRuntimeClient` is the transport boundary to Orket. Apophenia code must use the generic host endpoints for LLM and memory behavior.

## Local-First Contract

The BFF is local-first.

1. `config.bff.host` defaults to `127.0.0.1`.
2. Permitted BFF bind hosts are `127.0.0.1` and `::1`.
3. Any other BFF bind host must fail startup before binding.
4. `orket.base_url` host must be `127.0.0.1` or `::1` unless `[local_first_override].enabled = true`.
5. `localhost` is rejected when local-first override is disabled.
6. The BFF must make no intentional off-device network calls.

Default BFF port is `8090`.

## Authentication Contract

Bootstrap endpoint:

| Method | Path | Auth | Behavior |
|---|---|---|---|
| `GET` | `/bootstrap/token` | none | Loopback only. Returns persisted token. |

Token lifecycle:
1. Token is generated once with `secrets.token_urlsafe(32)`.
2. Token is persisted to `{config_dir}/bff.token`.
3. Token is reused across BFF restarts.
4. Token rotates only by manual deletion.

Protected endpoints require `X-Apophenia-Token`.

| Condition | Result |
|---|---|
| Missing or wrong token | `401` |
| Non-loopback bootstrap request | `403` |

## BFF API Contract

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET` | `/bootstrap/token` | no | Return persistent token |
| `GET` | `/config` | yes | Return nudge and memory config |
| `POST` | `/observe` | yes | Classify, store, return nudge instruction |
| `GET` | `/diagram/today` | yes | Return today's SVG or `404` |
| `POST` | `/diagram/generate` | yes | Trigger daily job idempotently |
| `GET` | `/status` | yes | Return health, observation count, job state |

## Date Authority

Session buckets use BFF local date.

1. `session_id` format is `apophenia.{YYYY-MM-DD}`.
2. The date is derived with `datetime.now().date()` in the BFF process.
3. Browser `timestamp_utc` is metadata only.
4. Browser payload timestamps must never derive `session_id`.
5. Daily job `today` is computed once at job start and passed through lower layers.

## Memory Contract

Observation writes use:

```text
scope:      episodic_memory
session_id: apophenia.{YYYY-MM-DD}
key:        obs.{uuid4}
```

Known behavior:
1. `memory_query` for an empty session returns `{ "records": [] }`.
2. `memory_write` and `memory_query` were live-verified through `HostRuntimeClient`.
3. Values through 64,000 chars were accepted and preserved with no truncation or rejection observed.
4. No host ceiling was found.
5. Do not claim an exact host ceiling.

`MAX_SUMMARY = 2000` is a conservative product choice, not a host limit.

## Truncation Contract

All Apophenia product truncation must produce strings of exactly `max_len` chars when truncation occurs.

```python
def _trunc(value: str, max_len: int) -> str:
    if len(value) > max_len:
        return value[:max_len - 1] + "…"
    return value
```

The ellipsis is one Unicode code point, so the returned string length remains exactly `max_len`.

Optional evidence strings use explicit null-normalization:

```python
def _optional_trunc(value: str | None, max_len: int) -> str | None:
    truncated = _trunc(value or "", max_len)
    return truncated or None
```

Empty optional evidence strings serialize as JSON `null`, not `""`.

## Product Limits

| Field | Product max | Applied in |
|---|---:|---|
| `memory_write` value summary | 2,000 | `ApopheniaApiClient._write_observation` |
| Evidence `observations[].summary` | 2,000 | `_write_evidence` |
| Evidence `support_atoms[].excerpt` | 200 | `_write_evidence` |
| Evidence `support_atoms[].claim` | 200 | `_write_evidence` |
| Evidence `rationale` | 1,000 | `_write_evidence` |
| Evidence `connection_label` | 50 | `_write_evidence` |
| `metadata.domain` | 100 | `ApopheniaApiClient._write_observation` |

## Content Handling

Tracked content:
1. Readable text of pages visited.
2. Scroll-weighted dwell signals.
3. SPA content via `MutationObserver`.
4. High-dwell blocks ranked higher in summaries.

Never tracked:
1. Medical, pharmacy, insurance, government, HR, payroll, or other life-administration content.
2. Work content identified by domain blocklist or content classifier.
3. Content when classifier fails.

Classifier behavior:
1. Stage 1 domain blocklist drops content with no LLM call.
2. Stage 2 classifier must return `interesting` or `administrative`.
3. Any classifier failure fails closed with no memory write.

## Privacy And Retention

| Artifact | Location | Content | Retention |
|---|---|---|---|
| Observations | Orket `episodic_memory` | Truncated summaries and metadata | 7 days |
| Daily SVG | User output dir | Domain label, 6-word excerpt, connection label | Indefinite |
| Evidence record | User output dir | Derived, schema-bounded audit data | Indefinite |
| BFF token | `{config_dir}/bff.token` | Random token | Persisted |
| BFF logs | Stderr only | No content logged | Session only |
| LLM prompt logs | Orket internals | Orket-retained prompts | Outside Apophenia control |
| Extension state | `chrome.storage.local` | Config, counters, timestamps | Cleared on uninstall |
| Blocklisted content | Never written | None | None |

Apophenia output files and BFF logs must contain no raw browsing content. Stored Apophenia content is LLM-derived and length-bounded.

## Observation Count Contract

1. Extension increments `chrome.storage.local["obs.count.{YYYY-MM-DD}"]` only after `/observe` returns `stored: true`.
2. Extension enforces max observation cap before sending content to the BFF.
3. Daily job uses `memory_query` result length as authoritative observation count.

## Nudge Contract

1. Nudge is body translate only: `4px`, `200ms` ease-out, return within `600ms`.
2. No zoom.
3. Abort nudge when active element is `INPUT`, `TEXTAREA`, `SELECT`, or `contenteditable`.
4. Global throttle is stored in `chrome.storage.local`.
5. Per-page lock is content-script memory.
6. `config.nudge.enabled = false` forces BFF responses to `nudge: false`.
7. BFF `/observe` response owns nudge decision.

## Daily Diagram Contract

One daily SVG may be produced. No diagram is preferable to unsupported output.

Output files:
1. `{diagram_dir}/{YYYY-MM-DD}.svg` is written only on success.
2. `{diagram_dir}/{YYYY-MM-DD}.evidence.json` is written at every daily-job exit point.
3. `{diagram_dir}/latest.json` is updated only after successful SVG write.

Connections are model-supported by evidence atoms, not independently verified facts.

Verification gate:
1. LLM pass 1 returns `{ label, rationale, support_atoms }`.
2. Every `support_atoms[].excerpt.lower()` must be a substring of its observation summary.
3. Any atom failure rejects the diagram.
4. LLM pass 2 verifier returns `supported`, `weak`, or `rejected`.
5. `weak` or `rejected` produces no SVG and no `latest.json` update.
6. `supported` plus zero atom failures may produce SVG.

Evidence reasons:
1. `supported`
2. `weak`
3. `rejected`
4. `deterministic_fail`
5. `insufficient_observations`
6. `no_observations`
7. `sanitizer_error`

## SVG Safety Contract

Server-side SVG generation:
1. Escape all text through `xml.sax.saxutils.escape()` before insertion.
2. Sanitize generated SVG before writing.
3. Use parent-map removal after traversal.
4. Attribute local name is authority.
5. Python namespaced attributes use Clark notation; derive local name with `attr.split("}")[-1] if "}" in attr else attr`.
6. Remove `script` and `foreignObject`.
7. Remove event-handler attributes.
8. Remove non-fragment `href` attributes.
9. Sanitizer failure writes evidence with `reason: sanitizer_error`, no SVG.

Client-side SVG safety:
1. Use `DOMParser` and `XMLSerializer`.
2. Use `attr.localName` for `href` checks.
3. Use `attr.name` for removal calls.
4. Remove `script`, `foreignObject`, event-handler attributes, and non-fragment hrefs.
5. Extension CSP is `default-src 'none'; script-src 'self'; style-src 'unsafe-inline'; connect-src http://127.0.0.1:8090 http://[::1]:8090`.

Live proof completed on 2026-05-08:
1. Browser proof for `DOMParser`, `XMLSerializer`, and `attr.localName` with `xlink:href` passed in headless Chrome.
2. Python environment proof with `defusedxml` installed passed through the structural suite and live diagram path.

## Dependencies

BFF dependencies:

```toml
fastapi>=0.110
uvicorn>=0.29
defusedxml>=0.7.1
pydantic>=2.0
toml>=0.10
```

Do not use `aiofiles` for Apophenia file writes. Use `asyncio.to_thread(path.write_text, ...)`.

The external implementation root owns its own dependency authority. Do not add Apophenia dependencies to Orket's `pyproject.toml` unless Apophenia code is explicitly implemented inside the Orket repo.

Extension dependency:

```json
{ "dependencies": { "@mozilla/readability": "0.6.0" } }
```

## Chrome Extension Contract

State storage:

| State | Storage |
|---|---|
| Nudge throttle timestamp | `chrome.storage.local` |
| Daily job fired flag | `chrome.storage.local` |
| Observation pre-filter count | `chrome.storage.local` |
| BFF auth token | `chrome.storage.local` |
| Daily job schedule | `chrome.alarms` |
| Retention schedule | `chrome.alarms` |
| Per-page nudge lock | Content script memory |

Chrome alarm IDs:
1. `apophenia.daily_job`
2. `apophenia.retention_purge`

## Configuration Contract

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

## Completed Phase Gates

Phase 0 completed on 2026-05-08:
1. This contract exists.
2. BFF bind, auth, token persistence, Orket URL validation, and `/config` are implemented and verified.

Phase 1 completed on 2026-05-08:
1. Phase 0 is verified.
2. Content classification, memory writes, truncation, count cap, and fail-closed classifier behavior are implemented and verified.

Phase 2 completed on 2026-05-08:
1. Phase 1 is verified.
2. Nudge behavior, throttle persistence, input safety, style cleanup, and kill switch are implemented and verified.

Phase 3 merge gates completed on 2026-05-08:
1. Real Apophenia observation records were created through `/observe`.
2. The diagram layout decision is constellation, not Venn.
3. Browser `DOMParser`/`attr.localName` sanitizer proof passed.
4. Python `defusedxml` sanitizer proof passed.

Companion memory is not a substitute for real Apophenia observation records in future layout changes.
