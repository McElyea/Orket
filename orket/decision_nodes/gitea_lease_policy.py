"""Pure lease body-limit policy over an explicitly captured environment."""
from collections.abc import Mapping

DEFAULT_ISSUE_BODY_MAX_BYTES = 65000


def gitea_issue_body_limit(environment: Mapping[str, str]) -> int:
    raw = str(environment.get("ORKET_GITEA_ISSUE_BODY_MAX_BYTES", DEFAULT_ISSUE_BODY_MAX_BYTES)).strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return DEFAULT_ISSUE_BODY_MAX_BYTES
