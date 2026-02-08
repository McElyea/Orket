from fastapi import APIRouter
from managers.alerting_manager import AlertingManager

router = APIRouter()

@router.post("/alert")
def create_alert(alert_config: dict):
    manager = AlertingManager()
    return manager.create_alert(alert_config)

@router.get("/alerts")
def get_alerts():
    manager = AlertingManager()
    return manager.get_alerts()