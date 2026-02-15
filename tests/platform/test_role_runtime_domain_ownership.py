from __future__ import annotations

import json
from pathlib import Path


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_role_runtime_domain_ownership_contract_is_valid():
    contract_path = Path("model") / "core" / "contracts" / "role_runtime_domain_ownership.json"
    contract = _load_json(contract_path)
    domains = contract.get("domains", {})
    assert isinstance(domains, dict) and domains, "domains must be a non-empty object."

    role_dir = Path("model") / "core" / "roles"
    role_names = {p.stem for p in role_dir.glob("*.json")}
    assert role_names, "No roles found under model/core/roles."

    errors: list[str] = []
    for domain_name, owners in domains.items():
        if not isinstance(owners, list) or not owners:
            errors.append(f"{domain_name}: owners must be a non-empty list.")
            continue
        if len(owners) > 2:
            errors.append(f"{domain_name}: owners exceed limit of 2 ({owners}).")
        for owner in owners:
            owner_name = str(owner).strip()
            if not owner_name:
                errors.append(f"{domain_name}: owner entry is empty.")
                continue
            if owner_name not in role_names:
                errors.append(f"{domain_name}: unknown role owner '{owner_name}'.")

    assert not errors, "\n".join(errors)


def test_canonical_pipeline_roles_have_single_owner_domains():
    contract_path = Path("model") / "core" / "contracts" / "role_runtime_domain_ownership.json"
    contract = _load_json(contract_path)
    domains = contract.get("domains", {})

    required_roles = {
        "requirements_analyst",
        "architect",
        "coder",
        "code_reviewer",
        "integrity_guard",
    }
    owner_counts = {role: 0 for role in required_roles}

    for owners in domains.values():
        if not isinstance(owners, list):
            continue
        for owner in owners:
            name = str(owner).strip()
            if name in owner_counts:
                owner_counts[name] += 1

    missing = sorted([role for role, count in owner_counts.items() if count == 0])
    assert not missing, f"Canonical roles missing ownership domains: {missing}"
