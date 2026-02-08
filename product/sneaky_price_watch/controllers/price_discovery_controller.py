from fastapi import APIRouter
from managers.price_discovery_manager import PriceDiscoveryManager

router = APIRouter()

@router.get("/discover")
def discover_prices():
    manager = PriceDiscoveryManager()
    return manager.discover()

@router.get("/alert")
def check_alerts():
    manager = PriceDiscoveryManager()
    return manager.alert()
