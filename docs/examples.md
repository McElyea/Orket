# McElyea Orket Examples (v0.3.5)

Professional configuration examples for the refactored Orket engine.

---

## 1. The McElyea Organization Card

The root source of truth for all projects.

```json
{
    "name": "McElyea",
    "ethos": "Excellence through iteration...",
    "branding": { "design_dos": ["Use clear labels"] },
    "architecture": { "idesign_threshold": 7 }
}
```

---

## 2. An Atomic Role (`lead_architect.json`)

Roles are now decoupled Cards (type: `utility`).

```json
{
    "id": "ARCH-ROLE",
    "name": "lead_architect",
    "type": "utility",
    "description": "System design lead",
    "prompt": "You are the Architect. Focus on volatility decomposition.",
    "tools": ["read_file", "list_directory"]
}
```

---

## 3. The Model Selector (Precedence)

How Orket chooses an LLM for a turn:
1.  `--model` (CLI Flag)
2.  `model_overrides` (Epic JSON)
3.  `preferred_coder` (User Settings)
4.  `default_llm` (Organization JSON)
5.  Ollama Fallbacks

---

## 4. Using Inter-Agent Notes

Agents can now "talk" across turns without global bloat.

```json
{
  "thought": "I need to let the coder know about the DB path.",
  "notes": ["BROADCAST: SQLite path is workspace/default/prices.db"],
  "tool_calls": [...]
}
```
