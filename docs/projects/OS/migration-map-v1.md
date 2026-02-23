# OS Migration Map v1

Last updated: 2026-02-22
Status: Normative migration map

| Current File | Future Module | Responsibility | Status |
|---|---|---|---|
| `tools/ci/orket_sentinel.py` | `orket/kernel/v1/validator.py` | 5-stage validation pipeline | Move |
| `tools/ci/orket_sentinel.py` | `orket/kernel/v1/events.py` | deterministic event emission contract | Refactor |
| `tools/ci/orket_map.py` | `orket/kernel/v1/observability/map.py` | structural visualization adapter | Optional Move |
| `tools/ci/test_sentinel.py` | `tests/kernel/v1/test_fire_drill.py` | kernel fire-drill verification | Rewrite |
| `tools/ci/fixtures/*` | `tests/kernel/v1/fixtures/*` | deterministic contract fixtures | Promote |
| `related_stems` plugin (in sentinel) | `orket/kernel/v1/plugins/related_stems.py` | connectivity extraction | Move |
| `orphan_links` plugin (in sentinel) | `orket/kernel/v1/plugins/orphan_links.py` | sovereign index integrity | Move |
| `orket/kernel/v1/state/lsi.py` | `orket/kernel/v1/state/lsi.py` | local sovereign index state model | Keep |
| `orket/kernel/v1/state/promotion.py` | `orket/kernel/v1/state/promotion.py` | promotion and commit semantics | Keep |
