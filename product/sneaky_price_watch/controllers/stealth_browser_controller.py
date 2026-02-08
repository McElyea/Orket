class StealthBrowserController:
    """
    Orchestrates the workflow for the stealth browser system.
    Manages the interaction between Managers, Engines, and Accessors.
    """
    def __init__(self, session_manager, config_manager, data_accessor):
        self.session_manager = session_manager
        self.config_manager = config_manager
        self.data_accessor = data_accessor

    def start_browsing_session(self, config):
        """
        Initiates a new browsing session based on the provided configuration.
        """
        session_id = self.session_manager.create_session(config)
        return session_id

    def end_browsing_session(self, session_id):
        """
        Ends the specified browsing session.
        """
        self.session_manager.end_session(session_id)

    def fetch_page_data(self, session_id, url):
        """
        Fetches data for a given URL within a session.
        """
        page_data = self.data_accessor.get_page_data(session_id, url)
        return page_data

    def update_session_config(self, session_id, new_config):
        """
        Updates the configuration for a given session.
        """
        self.config_manager.update_config(session_id, new_config)
