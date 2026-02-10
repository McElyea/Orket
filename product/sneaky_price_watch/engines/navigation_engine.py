class NavigationEngine:
    """
    Handles complex navigation logic and page fetching.
    """
    def __init__(self, http_client):
        self.http_client = http_client

    def fetch_page(self, session_id, url):
        """Fetches page content from a URL."""
        # Simulate fetching page content
        page_content = self.http_client.get(url)
        return {
            'url': url,
            'content': page_content,
            'session_id': session_id,
            'fetched_at': self._get_timestamp()
        }

    def _get_timestamp(self):
        """Returns current timestamp."""
        from datetime import datetime, UTC
        return datetime.now(UTC).isoformat()