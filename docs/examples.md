# Orket Examples (v0.3.6)

Configuration examples for the Orket engine.

---

## 1. Environment Secrets (`.env`)

Secrets are managed outside of the Card system for sovereignty.

```env
DASHBOARD_PASSWORD=your-secure-password
DASHBOARD_SECRET_KEY=your-secret-key
SD_MODEL=runwayml/stable-diffusion-v1-5
```

---

## 2. SRP-Compliant Issue (`IssueConfig`)

Issues now separate operational requirements from metrics and verification.

```json
{
    "id": "ISSUE-1234",
    "summary": "Implement price scraper",
    "seat": "coder",
    "requirements": "Create a robust scraper for target retail sites.",
    "verification": {
        "fixture_path": "tests/fixtures/scraper_test.py",
        "scenarios": [
            {
                "description": "Scrape valid URL",
                "input_data": {"url": "https://example.com"},
                "expected_output": {"price": 10.99}
            }
        ]
    },
    "metrics": {
        "shippability_threshold": 8.0
    }
}
```

---

## 3. Atomic Role (`roles/coder.json`)

Roles define the intent and toolset for a specific seat.

```json
{
    "id": "CODER-ROLE",
    "summary": "senior_developer",
    "type": "utility",
    "description": "Expert Python developer specializing in async I/O.",
    "prompt": "You are a Senior Developer. Write clean, PEP8 compliant code.",
    "tools": ["read_file", "write_file", "list_directory"]
}
```

---

## 4. The Unified Configuration Priority

How Orket loads assets in v0.3.6:
1.  **Unified Override:** `config/epics/my_epic.json`
2.  **Department Asset:** `model/marketing/epics/my_epic.json`
3.  **Core Fallback:** `model/core/epics/my_epic.json`

---

## 5. Model Provider with Retry

The engine handles transient failures automatically.

```python
# Internal logic example
provider = LocalModelProvider(model="qwen2.5-coder", timeout=60)
# complete() will retry 3x with exponential backoff on timeout/connection errors.
response = await provider.complete(messages)
```
