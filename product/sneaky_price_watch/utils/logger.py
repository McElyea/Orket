class Logger:
    """
    Provides cross-cutting logging functionality.
    Ensures consistent logging across the system.
    """
    def log(self, message):
        """Logs a message."""
        print(f"[LOG] {message}")