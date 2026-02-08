import unittest
from utils.http_client import HttpClient

class TestHttpClient(unittest.TestCase):
    def setUp(self):
        self.client = HttpClient()

    def test_get(self):
        response = self.client.get('https://example.com')
        self.assertIn('Content from', response)

    def test_post(self):
        response = self.client.post('https://example.com', {'key': 'value'})
        self.assertIn('Posted to', response)