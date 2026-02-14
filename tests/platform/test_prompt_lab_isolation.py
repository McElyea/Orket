from __future__ import annotations

from pathlib import Path


def test_runtime_does_not_import_prompt_lab_scripts() -> None:
    root = Path("orket")
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "from scripts.prompt_lab" in text or "import scripts.prompt_lab" in text:
            offenders.append(str(path).replace("\\", "/"))

    assert not offenders, (
        "Runtime layer must not import prompt_lab scripts.\n"
        + "\n".join(sorted(offenders))
    )
