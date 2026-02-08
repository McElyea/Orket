import unittest
from accessors.data_accessor import DataAccessor
from utils.storage import Storage

class TestDataAccessor(unittest.TestCase):
    def setUp(self):
        storage = Storage()
        self.accessor = DataAccessor(storage)

    def test_store_and_retrieve_page_data(self):
        page_data = {'url': 'https://example.com', 'content': 'Sample content', 'session_id': 'session123', 'fetched_at': '2026-02-07T21:00:00'}
        key = self.accessor.store_page_data('session123', page_data)
        retrieved_data = self.accessor.retrieve_session_data('session123')
        self.assertEqual(retrieved_data['url'], 'https://example.com')