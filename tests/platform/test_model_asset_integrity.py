from __future__ import annotations

import json
from pathlib import Path


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_prompt_metadata(metadata: dict, path: Path) -> list[str]:
    errors: list[str] = []
    prompt_id = str(metadata.get("id") or "").strip()
    version = str(metadata.get("version") or "").strip()
    status = str(metadata.get("status") or "").strip()
    if not prompt_id:
        errors.append(f"{path}: prompt_metadata.id missing.")
    if not version:
        errors.append(f"{path}: prompt_metadata.version missing.")
    if status not in {"draft", "candidate", "canary", "stable", "deprecated"}:
        errors.append(f"{path}: prompt_metadata.status invalid: {status!r}.")

    lineage = metadata.get("lineage")
    if not isinstance(lineage, dict):
        errors.append(f"{path}: prompt_metadata.lineage must be an object.")
    else:
        parent = lineage.get("parent")
        if parent is not None and not str(parent).strip():
            errors.append(f"{path}: prompt_metadata.lineage.parent must be null or non-empty.")

    changelog = metadata.get("changelog")
    if not isinstance(changelog, list) or not changelog:
        errors.append(f"{path}: prompt_metadata.changelog must be a non-empty list.")
    else:
        for idx, entry in enumerate(changelog):
            if not isinstance(entry, dict):
                errors.append(f"{path}: prompt_metadata.changelog[{idx}] must be an object.")
                continue
            if not str(entry.get("version") or "").strip():
                errors.append(f"{path}: prompt_metadata.changelog[{idx}].version missing.")
            if not str(entry.get("date") or "").strip():
                errors.append(f"{path}: prompt_metadata.changelog[{idx}].date missing.")
            if not str(entry.get("notes") or "").strip():
                errors.append(f"{path}: prompt_metadata.changelog[{idx}].notes missing.")
    return errors


def test_core_team_role_links_are_valid() -> None:
    root = Path("model") / "core"
    roles_dir = root / "roles"
    teams_dir = root / "teams"

    role_names = {p.stem for p in roles_dir.glob("*.json")}
    assert role_names, "No roles found under model/core/roles."

    errors: list[str] = []
    for team_path in sorted(teams_dir.glob("*.json")):
        team = _load_json(team_path)
        team_name = str(team.get("name") or team_path.stem)
        seats = team.get("seats") or {}
        if not isinstance(seats, dict):
            errors.append(f"{team_path}: seats must be an object.")
            continue
        for seat_name, seat_cfg in seats.items():
            roles = (seat_cfg or {}).get("roles") or []
            if not isinstance(roles, list):
                errors.append(f"{team_path}: seat '{seat_name}' roles must be a list.")
                continue
            for role_name in roles:
                if str(role_name) not in role_names:
                    errors.append(
                        f"{team_path}: team '{team_name}' seat '{seat_name}' references missing role '{role_name}'."
                    )

    assert not errors, "Invalid team->role links:\n" + "\n".join(errors)


def test_core_epic_team_and_seat_links_are_valid() -> None:
    root = Path("model") / "core"
    teams_dir = root / "teams"
    epics_dir = root / "epics"

    team_seats: dict[str, set[str]] = {}
    for team_path in sorted(teams_dir.glob("*.json")):
        team = _load_json(team_path)
        team_name = str(team.get("name") or team_path.stem)
        seats = team.get("seats") or {}
        if isinstance(seats, dict):
            team_seats[team_name] = set(seats.keys())

    assert team_seats, "No teams found under model/core/teams."

    errors: list[str] = []
    for epic_path in sorted(epics_dir.glob("*.json")):
        epic = _load_json(epic_path)
        epic_name = str(epic.get("name") or epic_path.stem)
        team_name = str(epic.get("team") or "").strip()
        if not team_name:
            errors.append(f"{epic_path}: epic '{epic_name}' missing team.")
            continue
        if team_name not in team_seats:
            errors.append(f"{epic_path}: epic '{epic_name}' references missing team '{team_name}'.")
            continue

        valid_seats = team_seats[team_name]
        issues = epic.get("issues") or []
        if not isinstance(issues, list):
            errors.append(f"{epic_path}: epic '{epic_name}' issues must be a list.")
            continue
        for issue in issues:
            issue_id = str((issue or {}).get("id") or "unknown")
            seat = str((issue or {}).get("seat") or "").strip()
            if not seat:
                errors.append(f"{epic_path}: epic '{epic_name}' issue '{issue_id}' missing seat.")
                continue
            if seat not in valid_seats:
                errors.append(
                    f"{epic_path}: epic '{epic_name}' issue '{issue_id}' uses seat '{seat}' not in team '{team_name}'."
                )

    assert not errors, "Invalid epic->team/seat links:\n" + "\n".join(errors)


def test_core_role_prompt_metadata_contract() -> None:
    roles_dir = Path("model") / "core" / "roles"
    errors: list[str] = []

    for role_path in sorted(roles_dir.glob("*.json")):
        role = _load_json(role_path)
        metadata = role.get("prompt_metadata")
        if not isinstance(metadata, dict):
            errors.append(f"{role_path}: missing prompt_metadata object.")
            continue

        errors.extend(_validate_prompt_metadata(metadata, role_path))

    assert not errors, "Invalid role prompt metadata:\n" + "\n".join(errors)


def test_core_dialect_prompt_metadata_contract() -> None:
    dialects_dir = Path("model") / "core" / "dialects"
    errors: list[str] = []

    for dialect_path in sorted(dialects_dir.glob("*.json")):
        dialect = _load_json(dialect_path)
        metadata = dialect.get("prompt_metadata")
        if not isinstance(metadata, dict):
            errors.append(f"{dialect_path}: missing prompt_metadata object.")
            continue

        errors.extend(_validate_prompt_metadata(metadata, dialect_path))

    assert not errors, "Invalid dialect prompt metadata:\n" + "\n".join(errors)


def test_core_standard_team_supports_canonical_pipeline_roles_and_seats() -> None:
    root = Path("model") / "core"
    roles_dir = root / "roles"
    standard_team_path = root / "teams" / "standard.json"
    standard = _load_json(standard_team_path)

    required_roles = {
        "requirements_analyst",
        "architect",
        "coder",
        "code_reviewer",
        "integrity_guard",
    }
    role_names = {p.stem for p in roles_dir.glob("*.json")}
    missing_roles = sorted(required_roles - role_names)
    assert not missing_roles, f"Missing canonical role assets: {missing_roles}"

    seats = standard.get("seats") or {}
    assert isinstance(seats, dict), "model/core/teams/standard.json: seats must be an object."
    missing_seats = sorted(required_roles - set(seats.keys()))
    assert not missing_seats, f"standard team missing canonical seats: {missing_seats}"

    seat_role_errors: list[str] = []
    for seat in sorted(required_roles):
        seat_cfg = seats.get(seat) or {}
        roles = seat_cfg.get("roles") or []
        if seat not in roles:
            seat_role_errors.append(
                f"standard seat '{seat}' must include role '{seat}' (current roles={roles})."
            )
    assert not seat_role_errors, "\n".join(seat_role_errors)


def test_fixture_acceptance_is_marked_secondary_to_canonical_flow() -> None:
    live_acceptance = Path("tests") / "live" / "test_system_acceptance_pipeline.py"
    fixture_acceptance = Path("tests") / "integration" / "test_system_acceptance_flow.py"
    assert live_acceptance.is_file(), "Canonical acceptance test file missing."
    assert fixture_acceptance.is_file(), "Fixture acceptance test file missing."
    text = fixture_acceptance.read_text(encoding="utf-8")
    assert "FIXTURE_SECONDARY = True" in text, (
        "Fixture acceptance tests must explicitly declare secondary status to canonical flow."
    )
