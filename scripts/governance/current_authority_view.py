"""Pure Markdown projection; source contracts retain their normative definitions."""

from __future__ import annotations

from urllib.parse import quote


def _cell(value: str) -> str:
    return (value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace("|", "\\|").replace("\n", " ").replace("\r", " ").replace("`", "\\`"))


def _link(path: str, label: str | None = None) -> str:
    return f"[{_cell(label or path)}](<{quote(path, safe='/._-#')}>)"


def _description(record: dict) -> str:
    kind = record["kind"]
    if kind == "command":
        return _cell(record["command"])
    if kind == "owners":
        return "; ".join(field + ": " + _link(record[field])
                         for field in ("executor", "authorization", "effect", "terminal"))
    if kind == "compatibility":
        expiry = record["expires_on"] or "condition-bound; no calendar expiry assigned"
        return _cell(record["condition"] + " (" + expiry + ")")
    if kind == "proof":
        observation = record["observed_on"] or "none"
        return _cell(record["state"] + "; observed " + observation + "; " + record["ceiling"])
    if kind == "ceiling":
        return _cell(record["posture"] + ": " + record["statement"])
    return _cell(record.get("scope", record.get("role", "")))


def render(payload: dict) -> bytes:
    lines = ["# Current authority", "", "Last updated: " + payload["updated_on"], "",
             "<!-- Generated from docs/architecture/current_authority.json; do not edit this view. -->", "",
             "This bounded index routes to canonical owners and contracts. It does not redefine their authority.",
             "Command checks compare documented argv and source entrypoints; they do not execute the commands.",
             "All listed proof is unavailable or historical. Current runtime acceptance is not established.", "",
             "Validate: `python scripts/governance/check_current_authority.py`.", ""]
    names = {"command": "Canonical commands", "owners": "Execution ownership", "reference": "Canonical indexes",
             "contract": "Active contracts", "compatibility": "Compatibility", "ceiling": "Claim ceilings",
             "proof": "Proof availability"}
    for kind, heading in names.items():
        rows = sorted((row for row in payload["records"] if row["kind"] == kind), key=lambda row: row["id"])
        if not rows:
            continue
        lines += ["## " + heading, "", "| Surface | Current scope | Source |", "| --- | --- | --- |"]
        for row in rows:
            description = _description(row)
            if kind == "owners":
                description += "; " + _cell(row["ceiling"])
            lines.append("| " + _cell(row["label"]) + " | " + description + " | " + _link(row["source"]) + " |")
        lines.append("")
    lines += ["## Retained history", "", _link(payload["history"]["path"], "Exact pre-cutover authority snapshot") +
              ". Historical statements are retained evidence, not current acceptance.", ""]
    output = "\n".join(lines).encode("utf-8")
    if len(output) > 32768 or len(lines) > 160:
        raise ValueError("generated authority exceeds 32KiB or 160 lines")
    return output
