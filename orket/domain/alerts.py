def evaluate_alert_conditions(alert):
    # Simple alert evaluation
    # In a real system, this would be more complex
    condition = alert["condition"]
    return "price" in condition and "<" in condition