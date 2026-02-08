import unittest
from utils.security_engine import SecurityEngine


class TestSecurityEngine(unittest.TestCase):
    def setUp(self):
        self.security_engine = SecurityEngine()

    def test_is_safe_url(self):
        # Test safe URL
        self.assertTrue(self.security_engine.is_safe_url("https://example.com"))
        
        # Test unsafe URL
        self.assertFalse(self.security_engine.is_safe_url("https://malware.example.com"))