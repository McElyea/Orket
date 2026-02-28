# Migration Map v1 (Normative)

## Purpose
Map current implementation to future kernel modules.
This prevents rewrite ambiguity and preserves ownership boundaries.

## Current -> Target mapping

| Current | Target | Responsibility | Rule |
|---|---|---|---|
| `tools/ci/orket_sentinel.py` | `orket/kernel/v1/validator.py` | 5-stage gatekeeper | Kernel owns law |
| sentinel logging | `orket/kernel/v1/contracts.py` + logger util | deterministic narrative | Logs are narrative stream |
| diff acquisition | CI layer (`tools/ci`) | diff sovereignty | Kernel must not require git |
| related_stems plugin | `orket/kernel/v1/plugins/related_stems.py` | connectivity helper | Optional module |
| orphan_links plugin | `orket/kernel/v1/state/lsi.py` + linking contract | link integrity | LSI is authority |
| fixtures | `tests/kernel/v1/` | constitutional scenarios | tests are law |

## Ownership boundaries
- Kernel v1 owns deterministic validation law and DTO shapes.
- LSI owns on-disk identity and linking integrity.
- Promotion owns atomic staging->committed and pruning law.
- CI tooling owns git diff and PR gating.

## Adapter policy
`tools/ci/orket_sentinel.py` may remain as a CLI adapter but MUST NOT remain the source of truth for kernel behavior once kernel/v1 modules exist.
