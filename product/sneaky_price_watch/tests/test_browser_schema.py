import unittest
from schemas.browser_schema import BrowserConfig, PageData, SessionData

class TestBrowserSchema(unittest.TestCase):
    def test_browser_config(self):
        config = BrowserConfig(
            user_agent='StealthBot/1.0',
            proxy='',
            incognito=True,
            timeout=30
        )
        self.assertEqual(config.user_agent, 'StealthBot/1.0')

    def test_page_data(self):
        page_data = PageData(
            url='https://example.com',
            content='Sample content',
            session_id='session123',
            fetched_at='2026-02-07T21:00:00'
        )
        self.assertEqual(page_data.url, 'https://example.com')

    def test_session_data(self):
        session_data = SessionData(
            config=BrowserConfig(user_agent='StealthBot/1.0', proxy='', incognito=True, timeout=30),
            created_at='2026-02-07T21:00:00',
            active=True
        )
        self.assertTrue(session_data.active)