from managers.price_discovery_manager import PriceDiscoveryManager
from engines.alerting_engine import AlertingEngine


class PriceAlertController:
    def __init__(self):
        self.manager = PriceDiscoveryManager()
        self.alert_engine = AlertingEngine()

    def setup_alerts(self, product_urls, threshold):
        # Sets up price alerting for given products
        current_prices = self.manager.discover_prices(product_urls)
        self.alert_engine.set_threshold(threshold)
        alerts = self.alert_engine.generate_alerts(current_prices)
        return alerts

    def monitor_prices(self, product_urls):
        # Monitors prices and triggers alerts
        current_prices = self.manager.discover_prices(product_urls)
        # In a real implementation, this would compare with previous prices
        alerts = self.alert_engine.generate_alerts(current_prices)
        return alerts