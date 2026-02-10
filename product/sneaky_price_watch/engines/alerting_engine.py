from typing import List, Dict, Any, Union

class AlertingEngine:
    def __init__(self):
        self.threshold = 0.0

    def set_threshold(self, threshold: float):
        self.threshold = threshold

    def generate_alerts(self, prices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        alerts = []
        for item in prices:
            price_val = item.get('price')
            if isinstance(price_val, (int, float)) and price_val > self.threshold:
                alerts.append(item)
        return alerts