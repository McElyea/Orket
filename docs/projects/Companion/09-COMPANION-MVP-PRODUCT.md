# Implementation Plan: Companion MVP Product Slice

**Parent**: 01-COMPANION-EXTERNAL-EXTENSION-PLAN.md
**Phase**: 2 (ship MVP)
**Depends on**: All Phase 0-1 plans (02 through 08)
**Estimated Scope**: ~25 files, ~2000 lines (Companion repo)

## Framing

This plan covers the Companion-side product implementation in the external repo. It assumes host-side execution seams already exist and are consumed through the public host API. The Companion app is a **thin client** over the host API seam. No product-significant runtime authority lives in the Companion repo.

## Backend Authority Model

For MVP, Companion product behavior primarily consumes public host API seams for:
- Generation (prompt assembly, memory retrieval, model dispatch)
- Memory retrieval/write
- Voice lifecycle
- Config/mode changes

The external repo includes an extension workload entrypoint (`workload.py`) for installability and manifest compatibility, but it is **thin compatibility infrastructure**, not a second hidden product authority. The host API `/chat` endpoint owns the full turn orchestration.

## Scope (from parent plan)

**MVP includes**:
- Real local web Companion chat experience
- Role/style selectors
- Voice controls including manual silence delay
- Memory controls (clear session, inspect/edit profile, memory toggle)
- Host-API-backed thin architecture
- Extensible presentation structure

**MVP excludes**:
- Audio output/TTS playback
- Adaptive cadence
- Episodic memory
- Avatar/emotion/lip-sync

## Implementation Steps

### Step 1: Thin workload entrypoint

```python
# src/companion_extension/workload.py

class CompanionWorkload:
    """
    Extension manifest compliance entrypoint.
    Real product behavior lives in the host API; this is compatibility infrastructure.
    """
    async def run(self, ctx: WorkloadContext, payload: dict) -> WorkloadResult:
        return WorkloadResult(ok=True, output={"type": "companion", "status": "host_api_driven"})
```

### Step 2: Host API client

```python
# src/companion_extension/api_client.py

class CompanionApiClient:
    """Typed client for consuming the host API seam. Companion-owned for MVP."""
    def __init__(self, base_url: str | None = None):
        self._base_url = base_url or os.environ.get("ORKET_HOST_URL", "http://localhost:8000")

    async def send_message(self, message: str) -> ChatResponse: ...
    async def get_config(self) -> CompanionConfig: ...
    async def update_mode(self, role_id: str, style: str) -> CompanionConfig: ...
    async def get_voice_state(self) -> TurnControlState: ...
    async def submit_voice(self) -> TurnControlState: ...
    async def transcribe_audio(self, audio_data: bytes) -> TranscribeResponse: ...
    async def clear_session_memory(self) -> None: ...
    async def get_status(self) -> CompanionStatusResponse: ...
```

The client orchestrates the end-user turn through the host API seam. It does not duplicate host-owned prompt assembly, memory retrieval, or generation.

### Step 3: Config loader

```python
# src/companion_extension/config_loader.py

class CompanionConfigLoader:
    """Load role/style JSON templates from config/ directory."""
    def load_role_template(self, role_id: str) -> dict: ...
    def load_style_modifiers(self, style_id: str) -> dict: ...
    def load_defaults(self) -> dict: ...
```

These templates define the extension-level config defaults (layer 1 of the precedence chain). The host uses them when assembling system prompts.

### Step 4: Web UI

**Requirements (outcome-oriented)**:
- Componentized: each UI section is self-contained
- Extensible toward richer presentation (avatar, expression) without replacement
- Thin in architecture: UI state and presentation only, no runtime authority
- Host-API-backed: all behavior flows through the host API client
- Real conversational experience, not a dev shell

**MVP tech choice**: Choose one simple serving model. Do not leave multiple frontend hosting patterns half-open.

**Core components** (regardless of framework choice):
- **Chat panel**: message list, text input, submit button, typing indicator, voice input toggle
- **Mode selector**: role dropdown (6 roles), style dropdown (4 styles), "pending next turn" indicator
- **Voice controls**: mic button, silence delay slider (0.5s-10.0s), voice state indicator, submit/cancel buttons, "voice unavailable" banner when STT is not available
- **Memory panel**: session/profile toggle, "clear session memory" button, profile viewer
- **Status bar**: connection status, STT availability, active model

### Step 5: Web UI -- voice interaction flow

1. User clicks mic -> UI starts recording via MediaRecorder API
2. User stops recording (or silence detected client-side) -> `POST /voice/transcribe` with audio blob
3. Host transcribes, returns text
4. Transcript appears in input field for review/editing
5. User submits (explicit button or silence-delay expiration via `POST /voice/submit`)
6. Host finalizes turn, returns response

"Voice unavailable" banner shown when `GET /voice/config` reports STT unavailable.

### Step 6: Web UI -- memory controls

- Session memory toggle (on/off) -> `PUT /config/memory`
- Profile memory toggle (on/off) -> `PUT /config/memory`
- "Clear session memory" button -> `DELETE /memory/session`
- "View profile" button -> modal with profile key/value list from `GET /memory/profile`
- Edit/delete individual profile entries -> `PUT/DELETE /memory/profile/{key}`

These are product features for end users, not debug utilities.

### Step 7: Dev server

Choose one simple MVP UI serving model:

```python
# src/companion_app/server.py
# Single choice: static file server with API proxy to host

def main():
    """
    Serves Companion web UI static files.
    Proxies /api/* to the Orket host API.
    """
```

### Step 8: Extensibility structure

Preserve room for future avatar/expression/lip-sync without dragging them into MVP. Concrete requirements:
- Component isolation: adding a new component does not require modifying existing ones
- Layout flexibility: room for a sidebar/overlay area that is currently empty
- No hard-coded assumptions about which components exist

Do not overprescribe the extensibility mechanism (event bus, slot system, etc.) before the MVP stack choice is finalized. Let the requirements drive the architecture.

## Acceptance Criteria

1. External extension execution with no internal Orket imports
2. Text path correctness when voice is disabled or STT unavailable
3. Manual silence-delay visibility, adjustability, and effect from UI
4. No turn finalization before configured silence window unless explicit user stop/submit
5. Intended settings round-trip through profile persistence
6. Real conversational experience (not a dev shell)
7. UI extensible toward future avatar/expression without replacement
8. Companion MVP product logic does not duplicate host-owned execution authority or create a second hidden backend outside the public seam

## Test Plan

**Unit tests** (Companion repo):
- Config loading: mode JSON files parse correctly
- API client: request/response serialization

**Contract tests** (Companion repo):
- Manifest validates against SDK schema
- Required capabilities are all satisfied
- Import scan passes

**Integration tests** (Companion repo, against running host):
- Chat round-trip: send message, get response
- Mode change: update mode, verify next turn uses new mode
- Memory: clear session, verify profile untouched
- Voice: transcribe audio, submit, verify transcript in chat
- Degradation: disable STT, verify text-only mode works
- Persistence: change profile setting, restart, verify setting persists

## Files to Create (Companion repo)

| Path | Description |
|------|-------------|
| `src/companion_extension/workload.py` | Thin compatibility entrypoint |
| `src/companion_extension/api_client.py` | Host API client (Companion-owned) |
| `src/companion_extension/config_schema.py` | Role/style enums + config models |
| `src/companion_extension/config_loader.py` | Load mode/style JSON configs |
| `src/companion_app/server.py` | Dev server (single serving model) |
| `src/companion_app/static/index.html` | SPA shell |
| `src/companion_app/static/app.js` | Main app logic |
| `src/companion_app/static/styles.css` | Styling |
| `config/modes/*.json` | 6 role template files |
| `config/styles/*.json` | 3+ style modifier files |
| `config/defaults.json` | Extension defaults |
| `tests/test_config_loading.py` | Unit tests |
| `tests/test_api_client.py` | Unit tests |
| `tests/test_integration_chat.py` | Integration tests |
| `tests/test_integration_memory.py` | Integration tests |
| `tests/test_integration_voice.py` | Integration tests |
