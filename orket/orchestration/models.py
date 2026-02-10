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
            return override

        # 2. Asset-level Override
        if asset_config and hasattr(asset_config, "params"):
            model_overrides = asset_config.params.get("model_overrides", {})
            if role in model_overrides:
                return model_overrides[role]

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
            return self.user_settings.get(pref_key)

        # 4. Organizational Standards
        if self.org and self.org.architecture.preferred_stack:
            # Check if role maps to a stack tier
            # (Simplified for now: Organization can define 'default_llm')
            org_default = self.org.process_rules.get("default_llm")
            if org_default:
                return org_default

        # 5. Hardcoded Fallbacks (The Safety Net)
        fallbacks = {
            "architect": "llama3.1:8b",
            "coder": "qwen2.5-coder:7b",
            "reviewer": "llama3.1:8b"
        }
        
        return fallbacks.get(role, "llama3.1:8b")

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
