"""Canonical LP-02 text normalization shared by messages and native render receipts."""


def canonicalize_prompt_text(value: str) -> str:
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip(" \t") for line in normalized.split("\n"))
