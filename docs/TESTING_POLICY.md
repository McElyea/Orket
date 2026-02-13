# Orket Testing Policy: "Real-World First"

## Philosophy: No-Mock Testing
We believe that mocks are often "liars"—they confirm that code *calls* something, but not that the code *works*. Orket favors **Sociable Tests** over **Isolated Tests**.

### 1. Don't Mock the Database
Use `aiosqlite` with a temporary file or `:memory:`. If a repository cannot handle a real SQLite connection in a test, the repository is broken.
*   **Bad**: `mock_repo.get_card.return_value = Card(...)`
*   **Good**: Create a real card in a temporary DB and retrieve it.

### 2. Don't Mock the Filesystem
Use pytest's `tmp_path` fixture. Tests should actually write bytes to disk and read them back. This catches permission issues, path traversal bugs, and encoding errors that mocks miss.

### 3. Use Simulators for External APIs
If we need to test Gitea integration, we hit a real Gitea instance (or a containerized simulator). If we must intercept HTTP, use `respx` or `httpx.ASGITransport` to route requests to a real (but local) FastAPI instance, rather than mocking the `requests.get` call.

### 4. LLM "Warm" Testing
While we don't hit paid APIs for every unit test, we should use a local, small model (like `phi3` or `tinyllama`) to verify that the `TurnExecutor` can actually parse a real response, rather than feeding it a hardcoded string.

### 5. When are Mocks allowed?
Mocks are a **last resort**, permitted ONLY for:
*   **Triggering Edge Cases**: Simulating a `500 Internal Server Error` from a 3rd party or a `TimeoutError`.
*   **Clock/Time**: Using `freezegun` to simulate time passing.
*   **Cost/Safety**: Preventing actual credit card charges or sending real emails to customers.

## Goal
A passing test suite should give us 95% confidence that the code is ready for production. Mock-heavy suites rarely exceed 50% confidence.

## CI Lane Policy
Use explicit lanes with fixed budgets.

1. `unit`
   - Command: `npm run ci:unit`
   - Scope: `tests/core`, `tests/application`, `tests/adapters`, `tests/interfaces`, `tests/platform`
   - Budget: <= 6 minutes
2. `integration`
   - Command: `npm run ci:integration`
   - Scope: `tests/integration`
   - Budget: <= 10 minutes
3. `acceptance`
   - Command: `npm run ci:acceptance`
   - Scope: acceptance-style integration + pipeline tests
   - Budget: <= 12 minutes
4. `live`
   - Command: `npm run ci:live`
   - Scope: `tests/live`
   - Budget: <= 20 minutes
   - Policy: opt-in only, excluded from default CI.
