# Implementation Plan: Config Schema and Mode Resolution

**Parent**: 01-COMPANION-EXTERNAL-EXTENSION-PLAN.md
**Phase**: 1 (SDK/host seam hardening)
**Depends on**: 02-SDK-PACKAGE-HARDENING
**Estimated Scope**: ~8 files touched, ~450 lines added

## Problem

Companion requires validated config schemas for role/style modes, memory toggles, and voice timing bounds. It also requires a 4-layer config precedence chain (extension defaults -> profile defaults -> session override -> pending next-turn override) that doesn't exist. Current config loading is file-based (organization JSON) with no extension-scoped config or mode resolution.

## Current State

**ConfigLoader** (`orket/runtime/config_loader.py`):
- Loads from `config/` -> `model/{dept}/` -> `model/core/` directories
- JSON-based organization and asset config
- No extension-scoped config
- No session-level or turn-level override mechanism

**Extension manifest config**:
- `WorkloadContext.config: dict[str, Any]` -- untyped passthrough
- No schema validation on extension config

**Mode/style concepts**: Do not exist anywhere in the codebase.

## Ownership Decision

**Companion config schema ownership must be decided explicitly**:

- If Companion config types (roles, styles, mode config) are **product-owned**, they live in the Companion external repo. The host API accepts/validates generic extension config via SDK-level contracts only.
- If they are **SDK-owned as reusable application-pattern primitives**, they live in `orket_extension_sdk/` and are importable by any extension.

**Recommended**: Product-owned in the Companion repo for MVP. The SDK provides generic config validation infrastructure (schema validation, precedence resolution). Companion-specific enums and schemas live in the Companion repo. Move to SDK only if a second extension needs the same patterns.

## Gap Analysis

| Gap | Severity | Detail |
|-----|----------|--------|
| No role/style mode schema | BLOCKING | Companion modes undefined in config |
| No config precedence chain | BLOCKING | No layered override mechanism |
| No extension config validation | HIGH | Config dict is untyped passthrough |
| No invalid combination blocking | HIGH | Role + style combos need validation at load and turn start |
| No mode change timing rules | MEDIUM | "Next-turn effective" rule has no enforcement |
| No config schema for voice bounds | MEDIUM | Silence-delay min/max not in config |
| No memory toggle in config | MEDIUM | Enable/disable has no config authority |

## Implementation Steps

### Step 1: Define role and relationship style enums

Location depends on ownership decision above. If product-owned (recommended):

```python
# Companion repo: src/companion_extension/config_schema.py

class CompanionRoleId(str, Enum):
    RESEARCHER = "researcher"
    PROGRAMMER = "programmer"
    STRATEGIST = "strategist"
    TUTOR = "tutor"
    SUPPORTIVE_LISTENER = "supportive_listener"
    GENERAL_ASSISTANT = "general_assistant"

class RelationshipStyleId(str, Enum):
    PLATONIC = "platonic"
    ROMANTIC = "romantic"
    INTERMEDIATE = "intermediate"
    CUSTOM = "custom"
```

### Step 2: Define Companion config schema (Pydantic)

```python
class CompanionModeConfig(BaseModel):
    role_id: CompanionRoleId = CompanionRoleId.GENERAL_ASSISTANT
    relationship_style: RelationshipStyleId = RelationshipStyleId.PLATONIC
    custom_style: dict[str, Any] | None = None  # only when style == CUSTOM

    @model_validator(mode="after")
    def validate_combination(self) -> Self:
        # Structural validation: custom_style required iff relationship_style == CUSTOM
        if self.relationship_style == RelationshipStyleId.CUSTOM and not self.custom_style:
            raise ValueError("custom_style required when relationship_style is custom")
        if self.relationship_style != RelationshipStyleId.CUSTOM and self.custom_style:
            raise ValueError("custom_style only allowed when relationship_style is custom")
        # Product-specific blocked combinations: empty in MVP (see Step 5)
        validate_mode_combination(self.role_id, self.relationship_style)
        return self

class CompanionMemoryConfig(BaseModel):
    session_memory_enabled: bool = True
    profile_memory_enabled: bool = True

class CompanionVoiceConfig(BaseModel):
    silence_delay_sec: float = 2.0
    silence_delay_min_sec: float = 0.5   # host-enforced floor
    silence_delay_max_sec: float = 10.0  # host-enforced ceiling

    @model_validator(mode="after")
    def clamp_delay(self) -> Self:
        self.silence_delay_sec = max(self.silence_delay_min_sec,
                                      min(self.silence_delay_max_sec, self.silence_delay_sec))
        return self

class CompanionConfig(BaseModel):
    mode: CompanionModeConfig = CompanionModeConfig()
    memory: CompanionMemoryConfig = CompanionMemoryConfig()
    voice: CompanionVoiceConfig = CompanionVoiceConfig()
```

### Step 3: 4-layer config precedence resolver

Merge semantics defined precisely:
- **Recursive merge by section** (mode, memory, voice are merged independently)
- **Lists are replaced, not appended** (no list merging)
- **Absent values mean "inherit from lower layer"** (not "clear")

```python
class ConfigPrecedenceResolver:
    """
    Precedence: extension_defaults < profile_defaults < session_override < pending_next_turn
    """
    def __init__(self):
        self._extension_defaults: dict = {}
        self._profile_defaults: dict = {}
        self._session_overrides: dict = {}
        self._pending_next_turn: dict = {}  # applied on next resolve(), then cleared

    def load_extension_defaults(self, config_dir: Path) -> None:
        """Load from extension's config/ directory (e.g., config/defaults.json)."""

    def load_profile_defaults(self, profile_memory: ScopedMemoryStore) -> None:
        """Load from profile_memory keys starting with companion_setting.*"""

    def set_session_override(self, section: str, value: Any) -> None:
        """Session-scoped override. Resets on new session."""

    def set_pending_next_turn(self, section: str, value: Any) -> None:
        """
        Queued for next turn. NOT current-turn effective.
        Applied on next resolve() call, then cleared.
        """

    def resolve(self) -> CompanionConfig:
        """Merge all layers (recursive per section), validate, return typed config."""
        merged = {}
        for layer in [self._extension_defaults, self._profile_defaults,
                      self._session_overrides, self._pending_next_turn]:
            recursive_section_merge(merged, layer)
        config = CompanionConfig.model_validate(merged)
        self._pending_next_turn.clear()  # consumed
        return config

    def clear_session(self) -> None:
        self._session_overrides.clear()
        self._pending_next_turn.clear()
```

### Step 4: Mode change timing enforcement

Plan says: "Mode/style changes are next-turn effective unless explicitly marked UI-only preview state."

The resolver uses `pending_next_turn` (not "turn override") to make the timing semantics unambiguous. A mode change request queues the change; it takes effect when `resolve()` is next called at turn start.

```python
class ModeChangePolicy:
    def apply_mode_change(self, resolver: ConfigPrecedenceResolver,
                          new_mode: CompanionModeConfig,
                          scope: Literal["session", "pending_next_turn"]) -> None:
        if scope == "session":
            resolver.set_session_override("mode", new_mode.model_dump())
        elif scope == "pending_next_turn":
            resolver.set_pending_next_turn("mode", new_mode.model_dump())
```

Mode/style change timing must be observable and testable through the full host/API/UI path, not only through internal resolver unit tests.

### Step 5: Invalid combination matrix

Blocked role/style combinations are not yet defined for MVP. State this explicitly:

```python
# Structural validation applies in MVP:
# - custom_style required iff style == CUSTOM
# Product-specific blocked combinations are empty for MVP.
# They will be populated when explicit product decisions are made.
BLOCKED_COMBINATIONS: set[tuple[CompanionRoleId, RelationshipStyleId]] = set()

def validate_mode_combination(role: CompanionRoleId, style: RelationshipStyleId) -> None:
    if (role, style) in BLOCKED_COMBINATIONS:
        raise ConfigValidationError(f"Blocked combination: {role} + {style}")
```

Structural validation (custom_style presence) is separate from policy/product validation (blocked combos).

Run validation at:
1. Config load (`CompanionConfig` Pydantic validator)
2. Turn start (before generation)
3. Mode change request (before persisting)

### Step 6: Extension config directory convention

Companion repo layout includes `config/modes/`. Define convention:
```
config/
  modes/
    researcher.json
    programmer.json
    ...
  defaults.json        # extension-level defaults for CompanionConfig
  styles/
    platonic.json
    romantic.json
    intermediate.json
```

## Acceptance Criteria

1. `CompanionConfig` validates with Pydantic; rejects unknown fields and structurally invalid state
2. Config precedence: extension < profile < session < pending_next_turn, verified by unit test
3. Merge semantics: recursive per section, lists replaced, absent = inherit
4. Structural validation (custom_style) active in MVP; product-specific blocked combinations explicitly empty
5. Mode changes are next-turn effective, observable through host API (not just resolver internals)
6. Session overrides reset on new session; pending_next_turn consumed and cleared after resolve()
7. Silence-delay bounds clamped by host
8. Memory toggles in config respected by memory subsystem

## Files to Create/Modify

| Action | Path | Notes |
|--------|------|-------|
| CREATE | Companion repo: `src/companion_extension/config_schema.py` | If product-owned (recommended) |
| CREATE | `orket/application/services/config_precedence_resolver.py` | Generic resolution infrastructure |
| CREATE | `orket/application/services/mode_change_policy.py` | |
| MODIFY | `orket/extensions/workload_executor.py` (validate extension config on load) | |
| CREATE | `tests/core/test_companion_config_schema.py` | Or in Companion repo |
| CREATE | `tests/application/test_config_precedence_resolver.py` | |
| CREATE | `tests/application/test_mode_change_timing_through_api.py` | Full path test |
| CREATE | `tests/application/test_config_merge_semantics.py` | |
