import unittest
from product.sneaky_price_watch.engines.alerting_engine import AlertingEngine


class TestAlerting(unittest.TestCase):
    def setUp(self):
        self.engine = AlertingEngine()

    def test_set_threshold(self):
        # Test setting alert threshold
        self.engine.set_threshold(100.0)
        self.assertEqual(self.engine.threshold, 100.0)

    def test_generate_alerts(self):
        # Test alert generation
        prices = [
            {'product_id': '1', 'price': 150.0},
            {'product_id': '2', 'price': 50.0}
        ]
        self.engine.set_threshold(100.0)
        alerts = self.engine.generate_alerts(prices)
        self.assertIsInstance(alerts, list)
        # Verify filtering logic works: only 150.0 > 100.0 should alert
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]['product_id'], '1')
