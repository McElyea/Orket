# TextMystery Layer 0 -- Gameplay Decisions and Checkpoint

Last updated: 2026-02-28
Status: Gameplay kernel substantially complete. SDK wiring not started.

This file contains TextMystery-specific gameplay decisions that informed Layer 0. These are game design decisions, not SDK contracts. The SDK is workload-agnostic.

## Locked Gameplay Decisions (D1-D13)

These decisions are locked for TextMystery v1. They do not constrain other workloads.

### D1: Fact payload shapes v1

7 typed payload shapes with explicit `kind`:
1. `time_anchor`: `{"kind":"time_anchor","time":"11:03 PM"}`
2. `presence`: `{"kind":"presence","who":"NICK_VALE","where":"SERVICE_DOOR","when":"11:03 PM"}`
3. `witness`: `{"kind":"witness","witness":"NADIA_BLOOM","who":"NICK_VALE","where":"SERVICE_DOOR","when":"11:03 PM"}`
4. `access_method`: `{"kind":"access_method","where":"SERVICE_DOOR","method":"KEYCARD"}`
5. `object`: `{"kind":"object","object":"AUDIT_DRIVE"}`
6. `action`: `{"kind":"action","who":"NICK_VALE","action":"MOVED","object":"AUDIT_DRIVE","when":"11:03 PM","where":"ARCHIVE"}`
7. `secret`: `{"kind":"secret","npc":"GABE_ROURKE","domain":"FINANCE","hint":"offbook expense sheet"}`

### D2: Render answer-shape validation gate

Renderer must enforce intent-to-shape compatibility:
- `WHERE_WAS` -> requires `where`
- `WHEN_WAS` -> requires `when` or `time`
- `DID_YOU_SEE` -> requires `who` or `witness`
- `WHO_HAD_ACCESS` -> from `access_graph`, never from `Fact.value`
- `DID_YOU_HAVE_ACCESS` -> boolean path, optional method text
- `WHAT_DO_YOU_KNOW_ABOUT` -> scoped summary and nudge topics only
- `UNCLASSIFIED_AMBIGUOUS` -> clarify response, never random factual output

### D3: Discovery/unlock model

Runtime discovery state: `discoveries: set[str]`
Frozen world lead map: `lead_unlocks: dict[str, list[str]]`
New evidence unlocks follow-up targets. Companion nudges prioritize undiscovered unlocks.

### D4: No universal noise rule

Universal `FACT_NOISE_1` forbidden. Each NPC has one secret fact. Controlled overlap by surface domain.

### D5: Workload context capability boundary

Workloads resolve dependencies via `ctx.capabilities`. No direct IO provider instantiation.

### D6: Fact payload includes explicit kind

All typed payloads must include `{"kind": "<type>", ...}`.

### D7: Canonical place/object IDs

Places: `SERVICE_DOOR`, `BOARDROOM`, `ARCHIVE`
Objects: `AUDIT_DRIVE`, `BOARDROOM_FEED`

### D8: Intent -> required fields validator mapping

Validator enforces per-intent field requirements to prevent place/object confusion in rendering.

### D9: Discovery keys are namespaced

Format: `disc:fact:<FACT_ID>`, `disc:place:<PLACE_ID>`, `disc:object:<OBJECT_ID>`, `disc:npc:<NPC_ID>`

### D10: Two-step triangulation

Culprit resolution requires at least two distinct discovered items (one witness claim + one presence/access claim).

### D11: Resolver matching (dynamic-first, deterministic)

Dynamic fact search before static fallback. Sorted `npc_knowledge` iteration for deterministic parity.

### D12: Companion hint policy (deterministic, non-repeating)

Hint markers (`disc:hint:<key>`), semantic repeat suppression, NPC-aware routing for access prompts.

### D13: Disambiguation command behavior

Accepts `back`, `help`, `quit`. Accepts numeric, named, and full-sentence angle choices.

---

## Implementation Checkpoint (as of 2026-02-28)

### Done

1. Typed facts with `kind` for all 7 shapes
2. `WHO_HAD_ACCESS` uses `access_graph` with `place_ref`
3. `DID_YOU_HAVE_ACCESS` is place-access only
4. Namespaced discovery keys recording in runtime
5. Discovery lead map in world model
6. UI disambiguation seam via `needs_disambiguation`
7. Runtime + CLI disambiguation path implemented
8. First-person render for speaker-owned facts with regression coverage
9. Cooperative-anchor rule active in worldgen
10. Resolver dynamic-first deterministic matching implemented and tested
11. Companion policy: semantic repeat suppression, nudge pacing, witness-chain-first, target markers, NPC-aware routing
12. Local deterministic test suite green

### Remaining (gameplay polish, not SDK blockers)

1. Companion quality pass: cross-suspect handoff wording and ranking, "already attempted" suppression
2. Clarify UX: place-scoped access clarifications with concrete choices
3. Tone/variation pass: DONT_KNOW/REFUSE phrase pools by intent

### Resume Checklist

1. Run `python -m pytest tests -q` in `C:\Source\Orket-Extensions\TextMystery`
2. Replay deterministic script (time, where, access-list, witness, object/action questions)
3. Inspect transcript: no raw IDs, witness/presence/access lines present
4. Continue from companion quality ranking pass

---

## Concrete Extraction Map (TextMystery -> SDK)

When SDK package is ready, these are the integration points:

| TextMystery File | SDK Integration |
|---|---|
| `engine/tts.py` | Extract interface to `AudioOutput` capability |
| `cli/main.py` | Replace direct provider with capability retrieval from context |
| `engine/worldgen.py` | Keep local; apply typed facts and invariants |
| `engine/render.py` | Keep local; typed fact rendering by intent |
| `engine/classify.py` | Keep local; stable `place_ref` and `object_id` extraction |
| `engine/persist.py` | Reuse SDK artifact helper API for digest/replay |
| `interfaces/live_contract.py` | Keep local; extract only generic trace/artifact helpers |
| `engine/runtime.py` | Keep local; inject infrastructure via `WorkloadContext` |

---

## Known Risks

1. Valid architecture does not guarantee play feel; bottleneck is companion quality, not truth engine.
2. Avoid broad SDK extraction during tuning unless proven generic across workloads.
3. Keep gameplay semantics in TextMystery; extract only stabilized infrastructure to SDK.
