from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class Panel:
    """A bordered region of text for terminal rendering."""

    title: str
    content: str
    width: int = 0  # 0 = auto-fit to content


@dataclass(frozen=True)
class TerminalSize:
    columns: int
    rows: int


@runtime_checkable
class ScreenRenderer(Protocol):
    """Minimal terminal rendering contract.

    Renders a list of panels. Input handling is NOT part of this protocol;
    the CLI collects input separately.
    """

    def render(self, panels: list[Panel]) -> None:
        ...

    def clear(self) -> None:
        ...

    def size(self) -> TerminalSize:
        ...


class NullScreenRenderer:
    """Plain-text fallback for CI and piped output."""

    def render(self, panels: list[Panel]) -> None:
        for panel in panels:
            if panel.title:
                print(f"--- {panel.title} ---")
            print(panel.content)
            print()

    def clear(self) -> None:
        pass

    def size(self) -> TerminalSize:
        return TerminalSize(columns=80, rows=24)
