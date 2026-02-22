# Orket Roadmap

Last updated: 2026-02-22

## Canonical Rule
`docs/ROADMAP.md` is the only active roadmap source.

## Priority Now
1. `modularize`: finalize living modularization docs and contract extraction quality.

## Project Index
Every non-archive project under `docs/projects/` must appear here.

| Project | Status | Priority | Canonical Path | Owner | Notes |
|---|---|---|---|---|---|
| modularize | active | P1 | `docs/projects/modularize/` | Orket Core | Current execution focus. |
| ideas | queued | P2 | `docs/projects/ideas/` | Orket Core | Working ideation/input material; not normative contracts. |
| archive | archive-root | n/a | `docs/projects/archive/` | Orket Core | Completed projects only. |

## Roadmap Policy
1. Keep only active and queued work in this file.
2. Do not maintain a second active backlog file.
3. When a project is complete, move related docs to `docs/projects/archive/<ProjectName>/`.
4. In the same change, update this index:
project status, canonical path, and any replaced links.
5. Do not keep long completed sections in active roadmap docs.

## Anti-Orphan Check
At handoff, verify both directions:
1. Every non-archive folder in `docs/projects/` exists in the Project Index.
2. Every `active` or `queued` Project Index entry points to an existing path.
