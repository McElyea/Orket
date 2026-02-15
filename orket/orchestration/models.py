from pathlib import Path
from typing import Dict, Any, Optional, List
import json

from orket.schema import OrganizationConfig, EpicConfig, RockConfig
from orket.settings import load_user_settings

class ModelSelector:
    """
    Centralized engine for selecting models based on organization standards,
    user preferences, and per-asset overrides.
    """
    def __init__(self, organization: Optional[OrganizationConfig] = None, user_settings: Optional[Dict[str, Any]] = None):
        self.org = organization
        self.user_settings = user_settings or load_user_settings()
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
        3. User Preferences (user_settings.json)
        4. Organizational Standards (organization.json)
        5. Hardcoded Fallbacks (The 'Safety Net')
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

        # 3. User Preferences
        # Map generic roles to preferred keys in user_settings.json
        pref_key_map = {
            "coder": "preferred_coder",
            "backend_specialist": "preferred_coder",
            "senior_developer": "preferred_coder",
            "lead_architect": "preferred_architect",
            "architect": "preferred_architect",
            "reviewer": "preferred_reviewer",
            "integrity_guard": "preferred_reviewer"
        }
        
        pref_key = pref_key_map.get(role)
        if pref_key and self.user_settings.get(pref_key):
            return self._apply_compliance_policy(role=role, selected_model=self.user_settings.get(pref_key))

        # 4. Organizational Standards
        if self.org and self.org.architecture.preferred_stack:
            # Check if role maps to a stack tier
            # (Simplified for now: Organization can define 'default_llm')
            org_default = self.org.process_rules.get("default_llm")
            if org_default:
                return self._apply_compliance_policy(role=role, selected_model=org_default)

        selected = self._fallback_model_for_role(role)
        return self._apply_compliance_policy(role=role, selected_model=selected)

    def get_last_selection_decision(self) -> Dict[str, Any]:
        return dict(self._last_selection_decision)

    def _fallback_model_for_role(self, role: str) -> str:
        fallbacks = {
            "architect": "llama3.1:8b",
            "coder": "qwen2.5-coder:7b",
            "reviewer": "llama3.1:8b",
        }
        return fallbacks.get(role, "llama3.1:8b")

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
