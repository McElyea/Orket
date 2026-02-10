import unittest
from unittest import IsolatedAsyncioTestCase
import pytest
from product.sneaky_price_watch.managers.price_discovery_manager import PriceDiscoveryManager


class TestPriceDiscovery(IsolatedAsyncioTestCase):
    def setUp(self):
        self.manager = PriceDiscoveryManager()

    async def test_discover_prices(self):
        # Test price discovery functionality
        urls = ['http://example.com/product1', 'http://example.com/product2']
        result = await self.manager.discover_prices(urls)
        self.assertIsInstance(result, list)

    def test_get_price_history(self):
        # Test price history retrieval
        result = self.manager.get_price_history('test_id')
        self.assertIsNotNone(result)