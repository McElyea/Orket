import re
from utils.price_utils import normalize_price

class PriceDiscoveryEngine:
    def __init__(self):
        self.price_pattern = re.compile(r'\$([0-9,]+\.?[0-9]*)')

    def process(self, raw_data):
        # Processes raw data to extract and normalize prices
        processed = []
        for item in raw_data:
            price_match = self.price_pattern.search(item['raw_text'])
            if price_match:
                price = normalize_price(price_match.group(1))
                processed.append({
                    'product_id': item['id'],
                    'price': price,
                    'timestamp': item['timestamp']
                })
        return processed

    def compare_prices(self, old_prices, new_prices):
        # Compares old and new prices to detect changes
        changes = []
        for new in new_prices:
            old = next((p for p in old_prices if p['product_id'] == new['product_id']), None)
            if old and old['price'] != new['price']:
                changes.append({
                    'product_id': new['product_id'],
                    'old_price': old['price'],
                    'new_price': new['price']
                })
        return changes