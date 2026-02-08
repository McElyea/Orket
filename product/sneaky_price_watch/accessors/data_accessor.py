class DataAccessor:
    """
    Manages data interaction with storage or external tools.
    """
    def __init__(self, storage):
        self.storage = storage

    def store_page_data(self, session_id, page_data):
        """Stores page data into persistent storage."""
        key = f"session:{session_id}:page_data"
        self.storage.set(key, page_data)
        return key

    def retrieve_session_data(self, session_id):
        """Retrieves all data associated with a session."""
        key = f"session:{session_id}:page_data"
        return self.storage.get(key)