from engines.alerting_engine import AlertingEngine
from accessors.alert_accessor import AlertAccessor


class AlertingManager:
    def __init__(self):
        self.engine = AlertingEngine()
        self.accessor = AlertAccessor()

    def create_alert(self, alert_config: dict):
        # Validate config
        alert = self.engine.validate_config(alert_config)
        
        # Store alert
        stored_alert = self.accessor.store_alert(alert)
        
        # Schedule alert check
        self.engine.schedule_alert_check(stored_alert)
        
        return stored_alert

    def get_alerts(self):
        return self.accessor.get_alerts()