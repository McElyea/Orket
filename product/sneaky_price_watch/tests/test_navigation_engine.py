import unittest
from engines.navigation_engine import NavigationEngine
from utils.http_client import HttpClient

class TestNavigationEngine(unittest.TestCase):
    def setUp(self):
        http_client = HttpClient()
        self.engine = NavigationEngine(http_client)

    def test_fetch_page(self):
        page_data = self.engine.fetch_page('session123', 'https://example.com')
        self.assertEqual(page_data['url'], 'https://example.com')
        self.assertIn('session123', page_data['session_id'])