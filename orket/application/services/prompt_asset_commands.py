"""Prompt policy and resolution inside the service's retained, guarded worker."""
from __future__ import annotations

from datetime import date
from typing import Any

from orket.adapters.storage.prompt_asset_store import PromptAssetStore
from orket.application.services.prompt_linter import lint_prompt_text
from orket.application.services.prompt_resolver import PromptResolver
from orket.core.contracts.prompt_assets import parse_prompt_id, prepare_prompt_metadata
from orket.schema import DialectConfig, RoleConfig, SkillConfig


class PromptAssetCommands:
    def __init__(self, store: PromptAssetStore, as_of: date):
        self.store, self.as_of = store, as_of

    def list(self, *, kind: str = "all", status: str = "") -> list[dict[str, Any]]:
        rows = []
        for selected in ("role", "dialect") if kind == "all" else (kind,):
            for path in self.store.paths(selected):
                metadata = self.store.read(path).get("prompt_metadata") or {}
                row = {"kind": selected, "name": path.stem, "path": str(path),
                       **{key: metadata.get(key) for key in ("id", "version", "status", "owner", "updated_at")}}
                if not status or str(row["status"] or "").strip() == status:
                    rows.append(row)
        return rows

    def show(self, *, prompt_id: str) -> dict[str, Any]:
        path = self.store.path(*parse_prompt_id(prompt_id))
        return {"path": str(path), "payload": self.store.read(path)}

    def lint(self) -> dict[str, Any]:
        violations = []
        for kind in ("role", "dialect"):
            for path in self.store.paths(kind):
                violations.extend(lint_prompt_text(path, self.store.content(path), kind))
        for item in violations:
            item["message"] = f"{str(item.get('file') or '').strip()}: [{item.get('rule_id')}] {str(item.get('message') or '').strip()}"
        errors = [item for item in violations if str(item.get("severity") or "") == "strict"]
        warnings = [item for item in violations if str(item.get("severity") or "") != "strict"]
        return {"ok": not errors, "error_count": len(errors), "warning_count": len(warnings),
                "errors": errors, "warnings": warnings, "violations": violations}

    def resolve(self, *, role: str, dialect: str, selection_policy: str = "stable", version_exact: str = "",
                strict: bool = True, profile: str = "default") -> dict[str, Any]:
        role_cfg = RoleConfig.model_validate(self.store.read(self.store.path("role", role)))
        dialect_cfg = DialectConfig.model_validate(self.store.read(self.store.path("dialect", dialect)))
        skill = SkillConfig(name=role_cfg.name or role, intent=role_cfg.description,
                            responsibilities=[role_cfg.description], tools=list(role_cfg.tools or []),
                            prompt_metadata=dict(role_cfg.prompt_metadata or {}))
        resolution = PromptResolver.resolve(skill=skill, dialect=dialect_cfg, selection_policy=selection_policy,
            context={"prompt_context_profile": profile, "prompt_resolver_policy": "resolver_v1",
                     "prompt_selection_policy": selection_policy, "prompt_selection_strict": bool(strict),
                     "prompt_version_exact": version_exact.strip()})
        return {"prompt": resolution.system_prompt, "metadata": resolution.metadata, "layers": resolution.layers}

    def update(self, *, prompt_id: str, mode: str, apply_changes: bool = False, **options: Any) -> dict[str, Any]:
        shown = self.show(prompt_id=prompt_id)
        payload, result = prepare_prompt_metadata(shown["payload"], prompt_id=prompt_id, mode=mode,
                                                   as_of=self.as_of, **options)
        path = self.store.path(*parse_prompt_id(prompt_id))
        if apply_changes:
            self.store.write(path, payload)
        return {"path": str(path), "apply_changes": bool(apply_changes), **result}

    def stale(self, *, max_candidate_age_days: int = 14) -> list[dict[str, Any]]:
        rows = []
        for row in self.list(status="candidate"):
            try:
                age = (self.as_of - date.fromisoformat(str(row.get("updated_at") or ""))).days
            except ValueError:
                age = None
            if age is None or age >= max_candidate_age_days:
                rows.append({**row, "age_days": age, "stale": True,
                             "reason": "updated_at_missing_or_invalid" if age is None else "candidate_age_exceeded"})
        return rows

    def enforce_sla(self, *, max_candidate_age_days: int = 14, renew_ids: list[str] | None = None,
                    apply_changes: bool = False) -> dict[str, Any]:
        renew = {str(value).strip() for value in (renew_ids or []) if str(value).strip()}
        stale = self.stale(max_candidate_age_days=max_candidate_age_days)
        if any(row.get("id") != f"{row['kind']}.{row['name']}" for row in stale):
            raise ValueError("E_PROMPT_METADATA_ID_MISMATCH")
        actions = []
        for row in stale:
            prompt_id = str(row.get("id") or "").strip()
            selected = prompt_id in renew
            note = f"SLA renewal at {self.as_of.isoformat()}." if selected else (
                f"SLA auto-deprecate at {self.as_of.isoformat()}: candidate age exceeded {max_candidate_age_days} days.")
            result = self.update(prompt_id=prompt_id, mode="promote" if selected else "deprecate",
                                 status="candidate" if selected else "", notes=note, apply_changes=apply_changes)
            actions.append({"id": prompt_id, "action": "renewed_candidate" if selected else "auto_deprecated",
                            "age_days": row["age_days"], "applied": bool(apply_changes), "result": result})
        renew_count = sum(row["action"] == "renewed_candidate" for row in actions)
        return {"ok": len(stale) == renew_count or bool(apply_changes), "as_of": self.as_of.isoformat(),
                "max_candidate_age_days": max_candidate_age_days, "stale_count": len(stale),
                "renew_count": renew_count, "deprecate_count": len(actions) - renew_count, "actions": actions}
