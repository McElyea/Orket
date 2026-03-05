# The Lie Detector

Date: 2026-03-01

## Purpose

"20 questions with a twist." Floor-progression deduction game where each character follows a truth policy. Player interviews characters about their life (favorite color, hometown, hobby, etc.), deduces the policy, then judges a single statement TRUE or FALSE. Correct judgment climbs the tower; incorrect falls. Hit the spikes = game over. Reach the top = escape.

**This is a standalone game.** It does not use TextMystery's crime-scene NPCs, world graph, or mystery facts. Characters are fresh, self-contained personas generated per seed.

## Status

v1 decoupling complete. Fully standalone persona system. No mystery-game dependencies. 57 tests passing.

## What Stays (Reusable Core)

These components are game-agnostic and remain unchanged:

| Component | Location | Why |
|-----------|----------|-----|
| TruthPolicy, should_be_truthful() | truth_policy.py | Pure deterministic policy. No world deps. |
| PolicyGate | truth_policy.py | Wraps TruthGate validation. Leak/lie inversion. |
| LieDetectorState, FloorState, judge_statement() | lie_detector.py | Floor progression + judgment. No world deps. |
| GameOutcome, PowerUpKind, InterviewTurn | lie_detector.py | Data types. |
| AnsiScreenRenderer | ansi_renderer.py | Panel rendering. Zero game deps. |
| SDK TUI protocol | orket_extension_sdk/tui.py | ScreenRenderer, Panel, etc. |

## What Changes (v1 Decoupling)

### Problem

The current `_ask_npc()` pipeline chains 6 mystery-specific systems:

```
classify_question()  -> mystery surface/intent taxonomy
resolve_answer()     -> mystery NPC knowledge graph
fact_phrase_for()    -> mystery fact rendering
build_npc_prompt()   -> mystery NPC archetype + personality
render_via_llm()     -> mystery truth gate context
generate_world()     -> mystery crime-scene world graph
```

None of these belong in a "20 questions" game about favorite colors and hometowns.

### Solution: Persona System

Replace the mystery pipeline with a self-contained persona system.

#### Persona Definition

Each character is a `Persona` — a frozen dataclass with a knowledge set of simple, verifiable facts:

```python
@dataclass(frozen=True)
class PersonaFact:
    topic: str          # e.g., "favorite_color", "hometown", "pet", "hobby"
    display_topic: str  # e.g., "favorite color", "hometown", "pet", "hobby"
    value: str          # e.g., "blue", "Portland", "tabby cat named Mochi", "rock climbing"

@dataclass(frozen=True)
class Persona:
    persona_id: str         # e.g., "DANA_CROSS"
    display_name: str       # e.g., "Dana Cross"
    archetype_id: str       # e.g., "LAID_BACK" — personality voice
    backstory: str          # One-line flavor text for LLM system prompt
    facts: tuple[PersonaFact, ...]  # 6-10 verifiable facts
```

#### Topic Taxonomy (replaces SurfaceId)

Simple topic strings instead of mystery-specific surface IDs:

```
favorite_color, hometown, pet, hobby, job, food, music,
travel, sibling, fear, childhood, morning_routine
```

TOPIC_SPLIT policies use these topics instead of SURF_TIME, SURF_WITNESS, etc.

#### Persona Generator

Deterministic (sha256-seeded, no random module). Given a seed, produces N unique personas by selecting from content pools:

```
content/lie_detector/
  personas.yaml     # Name pools, backstory templates, fact value pools
  archetypes.yaml   # Personality voices (reuse existing archetype system)
```

Each seed produces different name + fact combinations. Same seed = same game.

#### Interview Pipeline (replaces _ask_npc)

```
Player question
  |
  v
classify_topic(raw_question) -> topic string (keyword match)
  |
  v
resolve_persona_answer(persona, topic, must_lie) -> response text
  |  - If persona knows topic: return fact value (or lie)
  |  - If persona doesn't know topic: "I don't really have an answer for that."
  v
(Optional) LLM render with persona-specific prompt
  |  - System: "You are {name}. {backstory}. Personality: {archetype}."
  |  - If must_lie: "Contradict this fact: {fact_value}."
  |  - If truthful: "Convey this fact: {fact_value}."
  v
Response text
```

No WorldGraph. No resolve_answer. No fact_phrase_for. No classify_question.

#### Statement Generation (replaces _render_statement)

Pick a random PersonaFact. Render as a natural claim:

```
True:  "My favorite color is blue."
False: "My favorite color is red."  (pick alternative value from pool)
```

### File Plan

#### New Files

| File | Location | Purpose |
|------|----------|---------|
| `persona.py` | engine/ | Persona, PersonaFact, generate_personas(), classify_topic(), resolve_persona_answer() |
| `persona_prompt.py` | engine/ | build_persona_prompt() — LLM prompt for persona voice |
| `personas.yaml` | content/lie_detector/ | Name pools, backstory templates, fact value pools per topic |
| `archetypes.yaml` | content/lie_detector/ | Personality voices (can symlink or copy from mystery archetypes) |
| `test_persona.py` | tests/ | Persona generation determinism, topic classification, answer resolution |

#### Modified Files

| File | Change |
|------|--------|
| `lie_detector.py` | Replace `WorldGraph` dependency with `list[Persona]`. `generate_floors()` takes personas instead of world. `_render_statement()` uses PersonaFact. |
| `lie_detector_cli.py` | Replace mystery imports with persona imports. New `_ask_persona()` replaces `_ask_npc()`. Remove classify_question, resolve_answer, fact_phrase_for, generate_world. |
| `lie_detector.yaml` | Add topic pools, persona count config. |

#### Deleted Dependencies (from Lie Detector)

These remain in TextMystery for the mystery game but are no longer imported by Lie Detector:

- `classify_question()` — replaced by `classify_topic()`
- `resolve_answer()` — replaced by `resolve_persona_answer()`
- `fact_phrase_for()` — replaced by direct fact value access
- `generate_world()` — replaced by `generate_personas()`
- `build_npc_prompt()` — replaced by `build_persona_prompt()`

## Architecture (v1)

```
Seed
  |
  v
generate_personas(seed, count=12)   # Deterministic persona pool
  |
  v
generate_floors(seed, personas, total_floors=7)
  |  - Assign persona + policy per floor
  |  - Pick statement fact + truth/false
  v
For each floor:
  Interview loop (up to 5 Q&A):
    classify_topic(raw_question) -> topic
    should_be_truthful(policy, question_index, topic) -> must_lie
    resolve_persona_answer(persona, topic, must_lie) -> text
    (optional) LLM render via build_persona_prompt()
  |
  v
  Statement: "{display_name}: 'My {topic} is {value}.'"
  Player judges T/F
  judge_statement() -> climb/fall/win/game_over
```

## Truth Policies

Unchanged. Topics replace surfaces:

| Kind | Rule |
|------|------|
| ALWAYS_TRUTH | Every answer is factual |
| ALWAYS_LIE | Every answer contradicts facts |
| HALF_AND_HALF | Deterministic 50/50 per question (sha256-seeded) |
| TOPIC_SPLIT | Truthful about some topics, lies about others |

TOPIC_SPLIT example: truthful about `favorite_color` and `hometown`, lies about `pet` and `hobby`.

## Progression

Unchanged from v0:

- Start Floor 1, escape at Floor N (default 7)
- Correct judgment = climb 1 floor (early solve = climb 2)
- Wrong judgment = fall 1 floor, streak reset
- Streak of 3 = Oath Stone power-up
- Below Floor 1 = game over

## Power-Ups

- Oath Stone: Force one truthful answer regardless of policy
- Reveal: Show character's truth policy category

## Non-Negotiable Invariants

1. Policy evaluation is pure + deterministic (sha256, no random module)
2. Judgment uses persona facts, not LLM output
3. Same seed = same personas, same floors, same game
4. Characters are self-contained — no mystery-game knowledge required
5. Template mode (--no-llm) is fully playable with clear, varied responses

## Reforger Integration

Persona content YAML can be compiled through a new reforger route (`lie_detector_persona_v0`) that:
- Validates name/fact/archetype referential integrity
- Normalizes to canonical blob
- Materializes optimized YAML

This is optional for v1. Raw YAML loading is sufficient.

## Running (v1)

```
python scripts/MidTier/play_lie_detector.py --seed 42
python scripts/MidTier/play_lie_detector.py --seed 42 --plain --no-llm
```

## Implementation Phases

### Phase 1: Content + Persona Engine
- Create `content/lie_detector/personas.yaml` with name pools, backstory templates, fact value pools
- Create `engine/persona.py` with Persona, PersonaFact, generate_personas(), classify_topic(), resolve_persona_answer()
- Create `tests/test_persona.py`
- **Checkpoint**: generate_personas(seed=42) produces 12 unique personas deterministically

### Phase 2: Decouple lie_detector.py
- Replace WorldGraph/Fact imports with Persona/PersonaFact
- Rewrite generate_floors() to take personas instead of world
- Rewrite _render_statement() to use PersonaFact
- Update tests/test_lie_detector.py
- **Checkpoint**: All floor generation + judgment tests pass

### Phase 3: Decouple CLI
- Create `engine/persona_prompt.py` for LLM prompt building
- Rewrite lie_detector_cli.py: new _ask_persona(), remove mystery imports
- **Checkpoint**: `--no-llm --plain` mode fully playable with persona facts

### Phase 4: LLM Integration
- Wire persona prompts through render_via_llm (or a simplified version)
- **Checkpoint**: LLM mode produces in-character persona responses

### Phase 5: Polish
- Tune persona content (names, facts, backstories)
- Test across 10+ seeds for variety
- Update play_lie_detector.py if needed
