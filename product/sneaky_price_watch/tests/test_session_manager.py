import unittest
from managers.session_manager import SessionManager

class TestSessionManager(unittest.TestCase):
    def setUp(self):
        self.manager = SessionManager()

    def test_create_session(self):
        config = {'user_agent': 'StealthBot/1.0', 'proxy': '', 'incognito': True, 'timeout': 30}
        session_id = self.manager.create_session(config)
        self.assertIsNotNone(session_id)
        self.assertTrue(session_id in self.manager.sessions)

    def test_end_session(self):
        config = {'user_agent': 'StealthBot/1.0', 'proxy': '', 'incognito': True, 'timeout': 30}
        session_id = self.manager.create_session(config)
        self.manager.end_session(session_id)
        self.assertFalse(self.manager.sessions[session_id]['active'])