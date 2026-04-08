from __future__ import annotations


class ReviewError(RuntimeError):
    """Structured review-run failure for external command errors."""

    def __init__(
        self,
        message: str,
        *,
        command: list[str],
        returncode: int | None = None,
        stderr: str = "",
    ) -> None:
        self.command = list(command)
        self.returncode = returncode
        self.stderr = str(stderr or "")
        super().__init__(message)


__all__ = ["ReviewError"]
