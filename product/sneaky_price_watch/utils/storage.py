class Storage:
    """
    Utility for managing data persistence.
    """
    def __init__(self):
        self.data = {}

    def set(self, key, value):
        """Stores a value under the specified key."""
        self.data[key] = value

    def get(self, key):
        """Retrieves a value by key."""
        return self.data.get(key)