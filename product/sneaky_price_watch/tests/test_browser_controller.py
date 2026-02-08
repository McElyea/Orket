import unittest
from controllers.browser_controller import BrowserController
from managers.session_manager import SessionManager
from engines.navigation_engine import NavigationEngine
from accessors.data_accessor import DataAccessor
from utils.http_client import HttpClient
from utils.storage import Storage

class TestBrowserController(unittest.TestCase):
    def setUp(self):
        http_client = HttpClient()
        storage = Storage()
        session_manager = SessionManager()
        navigation_engine = NavigationEngine(http_client)
        data_accessor = DataAccessor(storage)
        self.controller = BrowserController(session_manager, navigation_engine, data_accessor)

    def test_start_session(self):
        config = {'user_agent': 'StealthBot/1.0', 'proxy': '', 'incognito': True, 'timeout': 30}
        session_id = self.controller.start_session(config)
        self.assertIsNotNone(session_id)

    def test_navigate_to(self):
        config = {'user_agent': 'StealthBot/1.0', 'proxy': '', 'incognito': True, 'timeout': 30}
        session_id = self.controller.start_session(config)
        result = self.controller.navigate_to(session_id, 'https://example.com')
        self.assertIsNotNone(result)

    def test_get_session_data(self):
        config = {'user_agent': 'StealthBot/1.0', 'proxy': '', 'incognito': True, 'timeout': 30}
        session_id = self.controller.start_session(config)
        self.controller.navigate_to(session_id, 'https://example.com')
        data = self.controller.get_session_data(session_id)
        self.assertIsNotNone(data)