def sanitize_name(name: str) -> str:
    """Converts 'Lead Architect' to 'lead_architect' for filenames and keys."""
    if not name: return "unknown"
    return name.lower().replace(" ", "_").strip()
