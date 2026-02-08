from fastapi import APIRouter
from managers.stealth_integration_manager import StealthIntegrationManager

router = APIRouter()

@router.get("/stealth/status")
def get_stealth_status():
    manager = StealthIntegrationManager()
    return manager.get_status()

@router.post("/stealth/activate")
def activate_stealth_mode():
    manager = StealthIntegrationManager()
    return manager.activate_stealth_mode()