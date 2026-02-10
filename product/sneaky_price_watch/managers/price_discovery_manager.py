from product.sneaky_price_watch.engines.price_discovery_engine import PriceDiscoveryEngine
from product.sneaky_price_watch.accessors.price_data_accessor import PriceDataAccessor

class PriceDiscoveryManager:
    def __init__(self):
        self.engine = PriceDiscoveryEngine()
        self.accessor = PriceDataAccessor()

    def discover_prices(self, product_urls):
        # Orchestrates the price discovery process
        raw_data = self.accessor.fetch_data(product_urls)
        processed_data = self.engine.process(raw_data)
        return processed_data

    def get_price_history(self, product_id):
        # Retrieves historical price data
        return self.accessor.get_history(product_id)