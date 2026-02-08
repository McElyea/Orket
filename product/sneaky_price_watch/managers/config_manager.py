class ConfigManager:
    """
    Manages configurations for browsing sessions.
    Handles the storage and retrieval of session-specific settings.
    """
    def __init__(self):
        self.configs = {}

    def update_config(self, session_id, new_config):
        """
        Updates the configuration for a given session.
        """
        if session_id in self.configs:
            self.configs[session_id].update(new_config)
        else:
            self.configs[session_id] = new_config

    def get_config(self, session_id):
        """
        Retrieves the configuration for a given session.
        """
        return self.configs.get(session_id, {})
