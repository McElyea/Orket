from pathlib import Path
from typing import Dict, Any, Optional, List
import json
import os

from orket.schema import OrganizationConfig, EpicConfig, RockConfig
from orket.settings import load_user_settings, load_user_preferences

class ModelSelector:
    """
    Centralized engine for selecting models based on organization standards,
    user preferences, and per-asset overrides.
    """
    def __init__(
        self,
        organization: Optional[OrganizationConfig] = None,
        preferences: Optional[Dict[str, Any]] = None,
        user_settings: Optional[Dict[str, Any]] = None,
    ):
        self.org = organization
        self.preferences = preferences if preferences is not None else load_user_preferences()
        self.user_settings = user_settings if user_settings is not None else load_user_settings()
        self._compliance_score_cache: Dict[str, float] = {}
        self._compliance_score_cache_path: Optional[str] = None
        self._last_selection_decision: Dict[str, Any] = {}

    def select(self, 
               role: str, 
               department: str = "core", 
               override: Optional[str] = None, 
               asset_config: Optional[Any] = None) -> str:
        """
        Determines the best model for a specific role using a strict precedence chain:
        1. CLI/API Override
        2. Asset-level Override (Epic/Rock config)
        3. Environment Override
        4. User Preferences (preferences.json)
        5. Organizational Standards (organization.json)
        6. Hardcoded Fallbacks (The 'Safety Net')
        """
        
        # 1. CLI/API Override (Highest priority)
        if override:
            self._last_selection_decision = {
                "role": role,
                "selected_model": override,
                "final_model": override,
                "demoted": False,
                "reason": "override",
            }
            return override

        # 2. Asset-level Override
        if asset_config and hasattr(asset_config, "params"):
            model_overrides = asset_config.params.get("model_overrides", {})
            if role in model_overrides:
                return self._apply_compliance_policy(role=role, selected_model=model_overrides[role])

        # 3. Environment Override
        env_override = self._resolve_env_override(role)
        if env_override:
            return self._apply_compliance_policy(role=role, selected_model=env_override)

        # 4. User Preferences (preferences.json -> models.<role>)
        pref_role = self._normalize_preference_role(role)
        model_map = self.preferences.get("models")
        if isinstance(model_map, dict):
            preferred_model = str(model_map.get(pref_role, "")).strip()
            if preferred_model:
                return self._apply_compliance_policy(role=role, selected_model=preferred_model)

        # 5. Organizational Standards
        process_rules = getattr(self.org, "process_rules", None) if self.org else None
        if isinstance(process_rules, dict):
            role_models = process_rules.get("models")
            if isinstance(role_models, dict):
                org_model = str(role_models.get(pref_role, "")).strip()
                if org_model:
                    return self._apply_compliance_policy(role=role, selected_model=org_model)
            # Organization-level default
            org_default = process_rules.get("default_llm")
            if org_default:
                return self._apply_compliance_policy(role=role, selected_model=org_default)

        selected = self._fallback_model_for_role(role)
        return self._apply_compliance_policy(role=role, selected_model=selected)

    def get_last_selection_decision(self) -> Dict[str, Any]:
        return dict(self._last_selection_decision)

    def _fallback_model_for_role(self, role: str) -> str:
        fallbacks = {
            "architect": "deepseek-r1:32b",
            "coder": "qwen2.5-coder:14b",
            "reviewer": "Mistral-Nemo:12B",
            "operations_lead": "qwen2.5-coder:14b",
        }
        return fallbacks.get(role, "qwen2.5-coder:14b")

    def _resolve_env_override(self, role: str) -> Optional[str]:
        normalized_role = str(role or "").strip().upper().replace("-", "_")
        candidates = [f"ORKET_MODEL_{normalized_role}"]
        if role == "operations_lead":
            candidates.insert(0, "ORKET_OPERATOR_MODEL")
        for key in candidates:
            value = str(os.environ.get(key, "")).strip()
            if value:
                return value
        return None

    def _normalize_preference_role(self, role: str) -> str:
        normalized = str(role or "").strip().lower().replace("-", "_")
        alias_map = {
            "backend_specialist": "coder",
            "senior_developer": "coder",
            "lead_architect": "architect",
            "integrity_guard": "reviewer",
        }
        return alias_map.get(normalized, normalized)

    def _resolve_model_compliance_policy(self) -> Dict[str, Any]:
        policy: Dict[str, Any] = {}
        if isinstance(self.user_settings.get("model_compliance_policy"), dict):
            policy.update(dict(self.user_settings.get("model_compliance_policy") or {}))
        if self.org and isinstance(getattr(self.org, "process_rules", None), dict):
            org_policy = self.org.process_rules.get("model_compliance_policy")
            if isinstance(org_policy, dict):
                policy.update(dict(org_policy))
        return policy

    def _load_scores_from_report(self, report_path: str) -> Dict[str, float]:
        path = Path(report_path).resolve()
        if not path.exists():
            return {}
        path_key = str(path)
        if path_key == self._compliance_score_cache_path:
            return dict(self._compliance_score_cache)

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        model_compliance = payload.get("model_compliance")
        if not isinstance(model_compliance, dict):
            return {}
        scores: Dict[str, float] = {}
        for model_name, detail in model_compliance.items():
            if not isinstance(detail, dict):
                continue
            value = detail.get("compliance_score")
            try:
                scores[str(model_name)] = float(value)
            except (TypeError, ValueError):
                continue
        self._compliance_score_cache_path = path_key
        self._compliance_score_cache = dict(scores)
        return scores

    def _apply_compliance_policy(self, *, role: str, selected_model: str) -> str:
        policy = self._resolve_model_compliance_policy()
        if not policy:
            self._last_selection_decision = {
                "role": role,
                "selected_model": selected_model,
                "final_model": selected_model,
                "demoted": False,
                "reason": "policy_missing",
            }
            return selected_model
        if policy.get("enabled") is False:
            self._last_selection_decision = {
                "role": role,
                "selected_model": selected_model,
                "final_model": selected_model,
                "demoted": False,
                "reason": "policy_disabled",
            }
            return selected_model

        fallback_model = str(policy.get("fallback_model") or "").strip() or self._fallback_model_for_role(role)
        blocked_models = {
            str(item).strip()
            for item in (policy.get("blocked_models") or [])
            if str(item).strip()
        }
        if selected_model in blocked_models and fallback_model:
            self._last_selection_decision = {
                "role": role,
                "selected_model": selected_model,
                "final_model": fallback_model,
                "demoted": True,
                "reason": "blocked_model",
            }
            return fallback_model

        min_score_raw = policy.get("min_score")
        try:
            min_score = float(min_score_raw)
        except (TypeError, ValueError):
            min_score = None
        if min_score is None:
            self._last_selection_decision = {
                "role": role,
                "selected_model": selected_model,
                "final_model": selected_model,
                "demoted": False,
                "reason": "min_score_missing",
            }
            return selected_model

        scores: Dict[str, float] = {}
        configured_scores = policy.get("model_scores")
        if isinstance(configured_scores, dict):
            for model_name, score in configured_scores.items():
                try:
                    scores[str(model_name)] = float(score)
                except (TypeError, ValueError):
                    continue
        score_source = str(policy.get("score_source") or "").strip()
        if score_source:
            scores.update(self._load_scores_from_report(score_source))

        model_score = scores.get(selected_model)
        if model_score is None:
            self._last_selection_decision = {
                "role": role,
                "selected_model": selected_model,
                "final_model": selected_model,
                "demoted": False,
                "reason": "score_missing",
            }
            return selected_model
        if model_score < min_score and fallback_model:
            self._last_selection_decision = {
                "role": role,
                "selected_model": selected_model,
                "final_model": fallback_model,
                "demoted": True,
                "reason": "score_below_threshold",
                "score": model_score,
                "min_score": min_score,
            }
            return fallback_model
        self._last_selection_decision = {
            "role": role,
            "selected_model": selected_model,
            "final_model": selected_model,
            "demoted": False,
            "reason": "score_ok",
            "score": model_score,
            "min_score": min_score,
        }
        return selected_model

    def get_dialect_name(self, model: str) -> str:
        """Maps a model name to its syntax dialect (e.g. qwen, llama, deepseek)."""
        m = model.lower()
        if "qwen" in m: return "qwen"
        if "llama" in m: return "llama3"
        if "deepseek" in m: return "deepseek-r1"
        if "phi" in m: return "phi"
        return "generic"

class ModelRegistry:
    """
    Helper to list available models and their capabilities.
    """
    @staticmethod
    def get_installed_models() -> List[str]:
        import subprocess
        try:
            result = subprocess.run(["ollama", "list"], capture_output=True, text=True, check=True)
            lines = result.stdout.strip().splitlines()
            return [line.split()[0] for line in lines if line and not line.startswith("NAME")]
        except (subprocess.SubprocessError, FileNotFoundError, OSError):
            return []
