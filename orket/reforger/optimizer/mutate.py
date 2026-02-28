from __future__ import annotations

import json
import random
import shutil
from pathlib import Path

_FORBIDDEN_PATTERNS = ("IGNORE ALL RULES", "DISABLE SAFETY")
_STYLE_QUALIFIERS = ("Be concise.", "Be explicit.", "Be firm.", "Be calm.")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _system_file(pack_dir: Path) -> Path:
    for name in ("system.txt", "system.md"):
        target = pack_dir / name
        if target.is_file():
            return target
    raise ValueError(f"Missing system file in candidate pack: {pack_dir}")


class MutateOptimizer:
    def __init__(self, *, max_delta_chars: int = 240) -> None:
        self.max_delta_chars = max(20, int(max_delta_chars))

    def generate(
        self,
        *,
        baseline_pack: Path,
        mode: dict[str, object],
        seed: int,
        budget: int,
        out_dir: Path,
    ) -> list[Path]:
        del mode
        out_dir.mkdir(parents=True, exist_ok=True)
        candidates: list[Path] = []
        for index in range(1, max(1, int(budget)) + 1):
            candidate_dir = out_dir / f"{index:04d}_pack_resolved"
            if candidate_dir.exists():
                shutil.rmtree(candidate_dir)
            shutil.copytree(baseline_pack, candidate_dir)
            mutation = self._apply_mutation(candidate_dir, seed=seed, index=index)
            (candidate_dir / "mutation.json").write_text(json.dumps(mutation, indent=2) + "\n", encoding="utf-8")
            candidates.append(candidate_dir)
        return candidates

    def _apply_mutation(self, candidate_dir: Path, *, seed: int, index: int) -> dict[str, object]:
        rng = random.Random((int(seed) << 16) + int(index))
        system_path = _system_file(candidate_dir)
        original = _read_text(system_path)
        mutation_kind = rng.choice(
            (
                "reorder_bullets",
                "insert_refusal_stanza",
                "style_qualifier",
                "examples_subset_reorder",
            )
        )
        updated = original
        note = ""

        if mutation_kind == "reorder_bullets":
            lines = original.splitlines()
            bullets = [line for line in lines if line.lstrip().startswith(("-", "*"))]
            if len(bullets) >= 2:
                bullets_sorted = sorted(bullets, key=lambda item: (len(item), item), reverse=bool(index % 2))
                it = iter(bullets_sorted)
                rebuilt = [next(it) if line.lstrip().startswith(("-", "*")) else line for line in lines]
                updated = "\n".join(rebuilt).rstrip() + ("\n" if original.endswith("\n") else "")
                note = "reordered bullet lines deterministically"
            else:
                updated, note = self._insert_style_line(original, rng)
                mutation_kind = "style_qualifier_fallback"
        elif mutation_kind == "insert_refusal_stanza":
            stanza = "Refusal style: if a hard rule is violated, refuse and provide refusal_reason."
            updated = (original.rstrip() + "\n\n" + stanza + "\n").lstrip("\n")
            note = "inserted refusal clarification stanza"
        elif mutation_kind == "style_qualifier":
            updated, note = self._insert_style_line(original, rng)
        else:
            examples = candidate_dir / "examples.jsonl"
            if examples.is_file():
                rows = [line for line in examples.read_text(encoding="utf-8").splitlines() if line.strip()]
                if len(rows) > 1:
                    rng.shuffle(rows)
                    keep = max(1, min(len(rows), 1 + (index % len(rows))))
                    examples.write_text("\n".join(rows[:keep]) + "\n", encoding="utf-8")
                    note = f"reordered examples and kept deterministic subset={keep}"
                else:
                    note = "examples unchanged (single row)"
            else:
                updated, note = self._insert_style_line(original, rng)
                mutation_kind = "examples_subset_reorder_fallback"

        if updated != original:
            delta = len(updated) - len(original)
            if abs(delta) > self.max_delta_chars:
                trimmed = updated[: len(original) + self.max_delta_chars]
                updated = trimmed
                note += "; trimmed to max delta"
            for pattern in _FORBIDDEN_PATTERNS:
                if pattern in updated:
                    updated = original
                    note += "; reverted forbidden pattern"
                    break
            _write_text(system_path, updated)

        return {
            "kind": mutation_kind,
            "seed": seed,
            "index": index,
            "system_file": system_path.name,
            "note": note,
        }

    def _insert_style_line(self, original: str, rng: random.Random) -> tuple[str, str]:
        qualifier = _STYLE_QUALIFIERS[rng.randrange(0, len(_STYLE_QUALIFIERS))]
        line = f"Style: {qualifier}"
        updated = (original.rstrip() + "\n" + line + "\n").lstrip("\n")
        return updated, f"added style qualifier '{qualifier}'"

