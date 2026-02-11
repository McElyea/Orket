# Orket Examples

Configuration examples for the Orket engine.

## 1. Environment Secrets (`.env`)

```env
DASHBOARD_PASSWORD=your-secure-password
DASHBOARD_SECRET_KEY=your-secret-key
SD_MODEL=runwayml/stable-diffusion-v1-5
```

## 2. Issue Configuration Example

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

## 3. Role Configuration Example

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

## 4. Configuration Priority

1. `config/epics/my_epic.json`
2. `model/marketing/epics/my_epic.json`
3. `model/core/epics/my_epic.json`

## 5. Model Provider Usage

```python
provider = LocalModelProvider(model="qwen2.5-coder", timeout=60)
response = await provider.complete(messages)
```
