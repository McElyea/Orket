# Contributing to Orket

Thank you for your interest in contributing to the Vibe Rail Orket EOS.

## Development Setup

1. **Clone the repository.**
2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Setup Environment:**
   Create a `.env` file for your local secrets (passwords, API keys).
4. **Run Orket:**
   ```bash
   python main.py --rock <rock_name>
   ```

## Project Structure

Orket follows the **Universal Card System**:
- **Rocks:** Strategic objectives (`model/core/rocks/`).
- **Epics:** Tactical feature groups (`model/core/epics/`).
- **Issues:** Operational units of work (found inside Epics).
- **Roles:** Personas and guidelines (`model/core/roles/`).
- **Dialects:** Model-specific syntax (`model/core/dialects/`).

## Adding a New Asset

### 1. Adding a Role
- Define identity and responsibilities in `model/core/roles/<role_name>.json`.
- Add relevant tools to the `tools` list.

### 2. Adding a Tool
- Implement the tool logic in a specialized class within `orket/tools.py` (e.g., `FileSystemTools`).
- Register the tool in the `ToolBox` and `get_tool_map`.
- Document security boundaries for the new tool.

### 3. Adding an Epic
- Define the team, environment, and atomic issues in `model/core/epics/<epic_name>.json`.
- Ensure issues follow the **Single Responsibility Principle (SRP)**.

## Coding Standards
- **Explicit Imports:** Avoid wildcard imports.
- **Async-First:** Use `async/await` for I/O and model interactions.
- **Type Safety:** Utilize Pydantic models for all configuration and state.
- **iDesign Compliance:** Adhere to Volatility Decomposition. Maintain separation between Managers, Engines, and Accessors.

## Pull Requests
- Include a clear description of changes.
- Add integration tests in the `tests/` directory.
- Update relevant documentation in `docs/`.
- Ensure `.env` and `*.db` files are never included.
