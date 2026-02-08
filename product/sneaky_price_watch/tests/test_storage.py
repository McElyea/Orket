import unittest
from utils.storage import Storage

class TestStorage(unittest.TestCase):
    def setUp(self):
        self.storage = Storage()

    def test_set_and_get(self):
        self.storage.set('test_key', 'test_value')
        value = self.storage.get('test_key')
        self.assertEqual(value, 'test_value')