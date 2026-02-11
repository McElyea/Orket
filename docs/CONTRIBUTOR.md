# Contributor Guide

This guide is human/agent agnostic.

## Read First
1. `docs/ROADMAP.md`
2. `docs/OrketArchitectureModel.md`
3. `docs/TESTING_POLICY.md`

## Quick Setup
1. Install dependencies: `pip install -r requirements.txt`
2. Create local `.env` for secrets.
3. Run locally: `python main.py --rock <rock_name>`

## Core Rules
1. Keep permanent decisions in tracked docs/code.
2. Keep runtime paths in `orket/` async-safe (no blocking I/O).
3. Keep governance mechanical (no retry theater).
4. Prefer small, reversible changes.
5. Do not commit secrets, `.env`, or local database files.

## Project Map
- Rocks: `model/core/rocks/`
- Epics: `model/core/epics/`
- Roles: `model/core/roles/`
- Dialects: `model/core/dialects/`

## How To Work
1. Pick one roadmap item.
2. Implement the smallest complete slice.
3. Add/update tests for behavior changed.
4. Run targeted tests first, then broader tests.
5. Update docs affected by behavior changes.

## Testing
1. Real-world first: prefer temporary real filesystems/databases over mocks.
2. Keep tests deterministic and isolated.
3. For refactors, prove parity with regression tests.

## Common Additions
1. New role: add `model/core/roles/<role>.json`.
2. New tool: implement in tool family/runtime seam and wire via decision strategy/tool map.
3. New epic: add `model/core/epics/<epic>.json` with atomic issues.

## PR Checklist
1. Clear summary of what changed and why.
2. Tests run and results listed.
3. Risk/rollback notes for non-trivial changes.
4. Docs updated where behavior changed.
