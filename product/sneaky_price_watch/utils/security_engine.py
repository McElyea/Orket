class SecurityEngine:
    """
    Provides security-related utilities for the stealth browser.
    Enforces safety protocols and threat detection.
    """
    def __init__(self):
        self.suspicious_patterns = ["malware", "phishing"]

    def is_safe_url(self, url):
        """Checks if a URL is safe."""
        # Simple check for suspicious patterns
        for pattern in self.suspicious_patterns:
            if pattern in url:
                return False
        return True