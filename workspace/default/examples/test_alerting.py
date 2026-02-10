import unittest
from engines.alerting_engine import AlertingEngine


class TestAlerting(unittest.TestCase):
    def setUp(self):
        self.engine = AlertingEngine()

    def test_set_threshold(self):
        # Test setting alert threshold
        self.engine.set_threshold(100.0)
        self.assertEqual(self.engine.threshold, 100.0)

    def test_generate_alerts(self):
        # Test alert generation
        prices = [{'product_id': '1', 'price': 150.0}]
        self.engine.set_threshold(100.0)
        alerts = self.engine.generate_alerts(prices)
        self.assertIsInstance(alerts, list)