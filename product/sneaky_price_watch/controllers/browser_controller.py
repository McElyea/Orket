class BrowserController:
    """
    Orchestrates the workflow for the stealth browser system.
    Manages the interaction between Managers, Engines, and Accessors.
    """
    def __init__(self, session_manager, navigation_engine, data_accessor):
        self.session_manager = session_manager
        self.navigation_engine = navigation_engine
        self.data_accessor = data_accessor

    def start_session(self, config):
        """Initiates a new browsing session."""
        session_id = self.session_manager.create_session(config)
        return session_id

    def navigate_to(self, session_id, url):
        """Navigates to a specified URL within a session."""
        page_data = self.navigation_engine.fetch_page(session_id, url)
        return self.data_accessor.store_page_data(session_id, page_data)

    def get_session_data(self, session_id):
        """Retrieves browsing session data."""
        return self.data_accessor.retrieve_session_data(session_id)