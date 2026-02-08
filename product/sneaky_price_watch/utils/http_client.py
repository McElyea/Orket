class HttpClient:
    """
    Utility for making HTTP requests.
    """
    def get(self, url):
        """Performs a GET request to the specified URL."""
        # Simulate HTTP GET request
        return f"Content from {url}"

    def post(self, url, data):
        """Performs a POST request to the specified URL."""
        # Simulate HTTP POST request
        return f"Posted to {url} with data: {data}"