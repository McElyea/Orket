import time

class StealthIntegrationEngine:
    def __init__(self):
        self.status = "normal"

    def get_status(self):
        return {"status": self.status}

    def activate_stealth_mode(self):
        # Simulate stealth mode activation
        self.status = "stealth"
        print("Stealth mode activated")
        
        # Add delay to simulate stealth behavior
        time.sleep(1)