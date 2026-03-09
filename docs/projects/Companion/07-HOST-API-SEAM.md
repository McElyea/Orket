# Implementation Plan: Host API Seam for Extensions

**Parent**: 01-COMPANION-EXTERNAL-EXTENSION-PLAN.md
**Phase**: 1-2 (seam hardening + MVP product)
**Depends on**: 03-CAPABILITY-WIRING, 04-MEMORY-SUBSYSTEM-SPLIT, 05-VOICE-STT-TURN-CONTROL, 06-CONFIG-AND-MODE-SCHEMA
**Estimated Scope**: ~10 files touched, ~800 lines added

## Scope Note

These routes are **Companion-scoped MVP host seams**. They are not yet a generalized extension-host API standard unless explicitly promoted later. The host API is the only runtime authority seam consumed by the Companion UI.

## Problem

Companion UI communicates with Orket exclusively through the host API seam. The current API (`orket/interfaces/api.py`) serves internal orchestration needs (sessions, cards, kernel, settings) but has no endpoints for: chat/generation, memory operations, voice control, config/mode management, or extension state. The Companion web app needs a sufficient API surface.

## Current State

**Existing API** (`orket/interfaces/api.py`):
- Session management, card CRUD, kernel, settings, system, streaming
- Internal orchestration focus; not designed for external extension consumption
- No CORS configuration for local web app
- No extension-scoped API namespace

**No existing**:
- Chat/generation endpoint
- Memory read/write endpoints
- Voice/STT endpoints
- Mode/config management endpoints
- Extension state endpoints
- API client for Companion to import

## Gap Analysis

| Gap | Severity | Detail |
|-----|----------|--------|
| No chat/generation endpoint | BLOCKING | Companion cannot send messages |
| No memory endpoints | BLOCKING | UI has no way to read/write/clear memory |
| No voice endpoints | BLOCKING | UI cannot control voice input |
| No config/mode endpoints | BLOCKING | UI cannot read/change modes |
| No CORS for local web app | BLOCKING | Browser will block requests |
| No API client package | HIGH | Companion web app needs typed client |
| No structured error responses | MEDIUM | Failures need consistent error codes |

## Implementation Steps

### Step 1: Define MVP-minimum endpoint set

Start with the minimum set needed for the Companion chat loop to work. Additional endpoints follow once the core loop is stable.

**MVP-minimum**:
```
/api/v1/companion/
  POST   /chat                  -> send message, get response (core loop)
  GET    /chat/history          -> session chat history
  POST   /chat/session          -> create new session
  DELETE /chat/session          -> end current session

  GET    /config                -> current resolved config
  PUT    /config/mode           -> change role/style (next-turn effective)

  GET    /voice/state           -> current turn control state
  POST   /voice/submit          -> explicit voice submit
  POST   /voice/transcribe      -> upload audio for transcription
  GET    /voice/config          -> voice config + STT availability

  DELETE /memory/session        -> clear session memory

  GET    /status                -> health, STT availability, config summary
```

**Additional (add when MVP core loop is stable)**:
```
  PUT    /config/voice          -> update voice settings
  PUT    /config/memory         -> update memory toggle settings
  POST   /voice/start           -> start listening
  POST   /voice/stop            -> stop listening
  POST   /voice/cancel          -> cancel voice input
  PUT    /voice/config          -> update silence delay
  GET    /memory/profile        -> query profile memory
  PUT    /memory/profile/{key}  -> write/update profile record
  DELETE /memory/profile/{key}  -> delete profile record
```

No endpoint should exist only because it is convenient internally. Every endpoint must serve the real Companion UI.

### Step 2: Create FastAPI router

```python
# orket/interfaces/routers/companion_router.py

from fastapi import APIRouter, HTTPException
router = APIRouter(prefix="/api/v1/companion", tags=["companion"])

@router.post("/chat")
async def send_message(request: ChatRequest) -> ChatResponse:
    """
    Send a user message and get a Companion response.
    Host-owned orchestration:
    1. Resolve config (4-layer precedence)
    2. Validate mode combination
    3. Retrieve session + profile memory (if enabled)
    4. Build messages (system prompt + memory context + history + user message)
    5. Call model.generate
    6. Write to session memory (if enabled)
    7. Consume pending_next_turn overrides
    8. Return response
    """
```

### Step 3: Chat request/response models

```python
class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    reply: str
    session_id: str
    turn_index: int
    model: str
    role_id: str
    style_id: str
    memory_used: bool
```

The chat endpoint owns the full turn orchestration. The Companion UI is a thin client that sends a message and receives a response. It does not duplicate prompt assembly, memory retrieval, or generation orchestration.

### Step 4: CORS configuration

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Configurable via env var `ORKET_COMPANION_CORS_ORIGINS` for custom ports.

### Step 5: Structured error responses

Structured error responses must align with existing host API error envelope conventions if they exist. If no convention exists, establish one here for Companion and recommend it as the standard.

```python
class CompanionErrorResponse(BaseModel):
    error_code: str
    message: str
    detail: dict[str, Any] | None = None

# Error codes
E_INVALID_MODE = "invalid_mode"
E_BLOCKED_COMBINATION = "blocked_combination"
E_MEMORY_DISABLED = "memory_disabled"
E_MEMORY_WRITE_DENIED = "memory_write_denied"
E_STT_UNAVAILABLE = "stt_unavailable"
E_VOICE_INVALID_STATE = "voice_invalid_state"
E_MODEL_UNAVAILABLE = "model_unavailable"
E_SESSION_NOT_FOUND = "session_not_found"
E_CONFIG_VALIDATION = "config_validation"
```

### Step 6: API client ownership decision

**Decide explicitly**: Is the typed Companion API client:
- **Companion-owned** in the external repo (recommended for MVP), or
- **SDK-owned** because this host seam is expected to be stable enough to expose broadly?

Avoid putting product-specific clients into the SDK too early. For MVP, the typed client lives in the Companion repo:

```python
# Companion repo: src/companion_extension/api_client.py

class CompanionApiClient:
    """Typed HTTP client for Companion web app to consume host API."""
    def __init__(self, base_url: str = "http://localhost:8000"):
        self._base_url = base_url

    async def send_message(self, message: str) -> ChatResponse: ...
    async def get_config(self) -> CompanionConfig: ...
    async def update_mode(self, role_id: str, style: str) -> CompanionConfig: ...
    async def get_voice_state(self) -> TurnControlState: ...
    async def clear_session_memory(self) -> None: ...
    async def get_status(self) -> CompanionStatusResponse: ...
```

### Step 7: Status endpoint

```python
@router.get("/status")
async def get_status() -> CompanionStatusResponse:
    return CompanionStatusResponse(
        healthy=True,
        stt_available=stt_provider.available,
        model_available=model_provider is not None,
        active_session_id=current_session_id,
        config_summary=resolver.resolve().model_dump(include={"mode", "memory"}),
    )
```

## Acceptance Criteria

1. All MVP-minimum endpoints reachable from local web app (CORS enabled)
2. `/chat` endpoint accepts message, returns response with resolved role/style, owning full turn orchestration
3. Memory endpoints respect toggle state and write policy; expose only user-facing MVP needs
4. Voice endpoints enforce FSM state transitions
5. Config endpoints validate combinations and enforce precedence
6. All error responses use structured `CompanionErrorResponse` with error codes aligned to existing conventions
7. API client usable from external Companion repo without internal imports
8. Status endpoint reports STT availability and model readiness
9. MVP host API surface remains minimal yet sufficient for the real Companion UI
10. No product-significant runtime authority lives outside the host API seam

## Files to Create/Modify

| Action | Path |
|--------|------|
| CREATE | `orket/interfaces/routers/companion_router.py` |
| CREATE | `orket/interfaces/routers/companion_models.py` (request/response schemas) |
| MODIFY | `orket/interfaces/api.py` (mount companion router, add CORS) |
| CREATE | `tests/interfaces/test_companion_chat_api.py` |
| CREATE | `tests/interfaces/test_companion_config_api.py` |
| CREATE | `tests/interfaces/test_companion_voice_api.py` |
| CREATE | `tests/interfaces/test_companion_cors.py` |
| CREATE | `tests/interfaces/test_companion_error_codes.py` |
