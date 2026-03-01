from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from orket.runtime_paths import durable_root

EXTENSION_ID = "meta.breaker.extension"
WORKLOAD_ID = "meta_breaker_v1"


def _extension_dir(project_root: Path) -> Path:
    return project_root / "workspace" / "live_ext" / "meta_breaker"


def _manifest_payload() -> dict[str, Any]:
    return {
        "manifest_version": "v0",
        "extension_id": EXTENSION_ID,
        "extension_version": "0.1.0",
        "workloads": [
            {
                "workload_id": WORKLOAD_ID,
                "entrypoint": "meta_breaker_extension:run_workload",
                "required_capabilities": [],
            }
        ],
    }


def _module_source() -> str:
    return """from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from orket_extension_sdk import ArtifactRef, WorkloadResult


ARCHETYPES = ("aggro", "control", "combo")
CARD_POOL = [
    # Aggro (10)
    {"id": "A01", "name": "Spark Raider", "archetype": "aggro", "cost": 1, "attack": 2, "health": 1},
    {"id": "A02", "name": "Street Blaze", "archetype": "aggro", "cost": 1, "attack": 2, "health": 1},
    {"id": "A03", "name": "Riot Drummer", "archetype": "aggro", "cost": 2, "attack": 3, "health": 2},
    {"id": "A04", "name": "Flashblade", "archetype": "aggro", "cost": 2, "attack": 3, "health": 1},
    {"id": "A05", "name": "Ember Scout", "archetype": "aggro", "cost": 2, "attack": 2, "health": 2},
    {"id": "A06", "name": "Rush Banner", "archetype": "aggro", "cost": 3, "attack": 4, "health": 2},
    {"id": "A07", "name": "Breakneck Wolf", "archetype": "aggro", "cost": 3, "attack": 4, "health": 3},
    {"id": "A08", "name": "Molten Axe", "archetype": "aggro", "cost": 3, "attack": 3, "health": 2},
    {"id": "A09", "name": "Burning Anthem", "archetype": "aggro", "cost": 4, "attack": 5, "health": 2},
    {"id": "A10", "name": "Final Charge", "archetype": "aggro", "cost": 4, "attack": 5, "health": 3},
    # Control (10)
    {"id": "C01", "name": "Ward Adept", "archetype": "control", "cost": 2, "attack": 1, "health": 4},
    {"id": "C02", "name": "Frost Snare", "archetype": "control", "cost": 2, "attack": 1, "health": 5},
    {"id": "C03", "name": "Shield Archivist", "archetype": "control", "cost": 3, "attack": 2, "health": 5},
    {"id": "C04", "name": "Null Barrier", "archetype": "control", "cost": 3, "attack": 1, "health": 6},
    {"id": "C05", "name": "Tempo Arrest", "archetype": "control", "cost": 3, "attack": 2, "health": 4},
    {"id": "C06", "name": "Mirror Warden", "archetype": "control", "cost": 4, "attack": 3, "health": 6},
    {"id": "C07", "name": "Arc Lock", "archetype": "control", "cost": 4, "attack": 2, "health": 7},
    {"id": "C08", "name": "Late Verdict", "archetype": "control", "cost": 5, "attack": 3, "health": 7},
    {"id": "C09", "name": "Silence Dome", "archetype": "control", "cost": 5, "attack": 2, "health": 8},
    {"id": "C10", "name": "Omega Seal", "archetype": "control", "cost": 6, "attack": 3, "health": 9},
    # Combo (10)
    {"id": "M01", "name": "Rune Weaver", "archetype": "combo", "cost": 1, "attack": 1, "health": 2},
    {"id": "M02", "name": "Chain Spark", "archetype": "combo", "cost": 1, "attack": 1, "health": 2},
    {"id": "M03", "name": "Relay Node", "archetype": "combo", "cost": 2, "attack": 2, "health": 2},
    {"id": "M04", "name": "Echo Sigil", "archetype": "combo", "cost": 2, "attack": 2, "health": 3},
    {"id": "M05", "name": "Link Curator", "archetype": "combo", "cost": 3, "attack": 2, "health": 4},
    {"id": "M06", "name": "Pattern Burst", "archetype": "combo", "cost": 3, "attack": 3, "health": 3},
    {"id": "M07", "name": "Loop Architect", "archetype": "combo", "cost": 4, "attack": 3, "health": 4},
    {"id": "M08", "name": "Spell Lattice", "archetype": "combo", "cost": 4, "attack": 4, "health": 4},
    {"id": "M09", "name": "Convergence Core", "archetype": "combo", "cost": 5, "attack": 4, "health": 5},
    {"id": "M10", "name": "Infinite Draft", "archetype": "combo", "cost": 6, "attack": 5, "health": 5},
]

# Base win probability of row archetype against column archetype.
BASE_MATCHUPS = {
    ("aggro", "aggro"): 0.50,
    ("aggro", "control"): 0.54,
    ("aggro", "combo"): 0.48,
    ("control", "aggro"): 0.46,
    ("control", "control"): 0.50,
    ("control", "combo"): 0.56,
    ("combo", "aggro"): 0.52,
    ("combo", "control"): 0.44,
    ("combo", "combo"): 0.50,
}


def run_workload(ctx, input_payload: dict[str, Any]) -> WorkloadResult:
    first_player_advantage = float(input_payload.get("first_player_advantage", 0.02) or 0.02)
    dominant_threshold = float(input_payload.get("dominant_threshold", 0.55) or 0.55)
    loop_threshold = int(input_payload.get("loop_threshold", 2) or 2)
    noise = (int(ctx.seed) % 5) * 0.001  # deterministic small perturbation for seed-tagged runs

    matchup_matrix: dict[str, dict[str, float]] = {}
    aggregate: dict[str, float] = {}
    dominant: list[str] = []
    for left in ARCHETYPES:
        row: dict[str, float] = {}
        wins = 0.0
        for right in ARCHETYPES:
            base = float(BASE_MATCHUPS[(left, right)])
            adjusted = min(0.99, max(0.01, base + first_player_advantage + noise))
            adjusted = round(adjusted, 3)
            row[right] = adjusted
            wins += adjusted
        matchup_matrix[left] = row
        avg = round(wins / len(ARCHETYPES), 3)
        aggregate[left] = avg
        if avg >= dominant_threshold:
            dominant.append(left)
    loop_detected = _detect_loop_risk(loop_threshold=loop_threshold)
    card_counts = _count_cards_by_archetype()

    report = {
        "seed": int(ctx.seed),
        "first_player_advantage": round(first_player_advantage, 3),
        "dominant_threshold": round(dominant_threshold, 3),
        "loop_threshold": loop_threshold,
        "archetypes": list(ARCHETYPES),
        "card_pool_size": len(CARD_POOL),
        "card_counts": card_counts,
        "matchup_matrix": matchup_matrix,
        "aggregate_win_rates": aggregate,
        "findings": {
            "dominant_archetypes": sorted(dominant),
            "loop_detected": loop_detected,
            "balance_status": "imbalanced" if dominant or loop_detected else "stable",
        },
    }
    out_path = Path(ctx.output_dir) / "meta_breaker_report.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    digest = hashlib.sha256(out_path.read_bytes()).hexdigest()
    return WorkloadResult(
        ok=True,
        output=report,
        artifacts=[ArtifactRef(path="meta_breaker_report.json", digest_sha256=digest, kind="meta_breaker_report")],
    )


def _count_cards_by_archetype() -> dict[str, int]:
    counts = {arch: 0 for arch in ARCHETYPES}
    for card in CARD_POOL:
        archetype = str(card.get("archetype", "")).strip()
        if archetype in counts:
            counts[archetype] += 1
    return counts


def _detect_loop_risk(*, loop_threshold: int) -> bool:
    # Toy deterministic loop signal: count explicit loop-tagged combo cards.
    loop_cards = [card for card in CARD_POOL if "Loop" in str(card.get("name", "")) or "Infinite" in str(card.get("name", ""))]
    return len(loop_cards) >= max(1, int(loop_threshold))
"""


def _catalog_path() -> Path:
    path = durable_root() / "config" / "extensions_catalog.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps({"extensions": []}, indent=2), encoding="utf-8")
    return path


def main() -> int:
    extension_dir = _extension_dir(PROJECT_ROOT)
    extension_dir.mkdir(parents=True, exist_ok=True)

    manifest = _manifest_payload()
    manifest_path = extension_dir / "extension.yaml"
    module_path = extension_dir / "meta_breaker_extension.py"
    manifest_path.write_text(
        "\n".join(
            [
                f"manifest_version: {manifest['manifest_version']}",
                f"extension_id: {manifest['extension_id']}",
                f"extension_version: {manifest['extension_version']}",
                "workloads:",
                f"  - workload_id: {manifest['workloads'][0]['workload_id']}",
                f"    entrypoint: {manifest['workloads'][0]['entrypoint']}",
                "    required_capabilities: []",
            ]
        ),
        encoding="utf-8",
    )
    module_path.write_text(_module_source(), encoding="utf-8")

    catalog_path = _catalog_path()
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    rows = payload.get("extensions") if isinstance(payload.get("extensions"), list) else []
    rows = [row for row in rows if not (isinstance(row, dict) and str(row.get("extension_id")) == EXTENSION_ID)]
    rows.append(
        {
            "extension_id": EXTENSION_ID,
            "extension_version": "0.1.0",
            "extension_api_version": "v0",
            "contract_style": "sdk_v0",
            "source": "workspace/live_ext/meta_breaker",
            "path": str(extension_dir),
            "manifest_path": str(manifest_path),
            "workloads": [
                {
                    "workload_id": WORKLOAD_ID,
                    "workload_version": "0.1.0",
                    "entrypoint": "meta_breaker_extension:run_workload",
                    "required_capabilities": [],
                    "contract_style": "sdk_v0",
                }
            ],
        }
    )
    payload["extensions"] = rows
    catalog_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    print(f"Registered extension_id={EXTENSION_ID} workload_id={WORKLOAD_ID}")
    print(f"Catalog: {catalog_path}")
    print(f"Module: {module_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
