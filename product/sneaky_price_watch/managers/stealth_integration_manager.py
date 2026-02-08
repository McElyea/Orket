from engines.stealth_integration_engine import StealthIntegrationEngine
from accessors.stealth_accessor import StealthAccessor


class StealthIntegrationManager:
    def __init__(self):
        self.engine = StealthIntegrationEngine()
        self.accessor = StealthAccessor()

    def get_status(self):
        return self.engine.get_status()

    def activate_stealth_mode(self):
        # Activate stealth mode
        self.engine.activate_stealth_mode()
        
        # Update system state
        self.accessor.update_system_state("stealth_mode", True)
        
        return {"status": "stealth mode activated"}