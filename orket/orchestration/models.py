from orket.runtime.config.provider_discovery import installed_models


class ModelRegistry:
    """
    Helper to list available models and their capabilities.
    """

    @staticmethod
    def get_installed_models() -> list[str]:
        return installed_models()
