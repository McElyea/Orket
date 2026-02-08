from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
import asyncio
import random
from datetime import datetime
from .models import Target, PriceHistory, GlobalSettings
from .scraper import PriceScraper

app = FastAPI(title="Orket Arbitrage Backend")
scraper = PriceScraper()

class TargetCreate(BaseModel):
    name: str
    url: str
    selector_type: str
    selector_value: str
    market_baseline: float = None
    threshold_percent: float = 20.0

@app.post("/targets")
async def add_target(target: TargetCreate):
    # Logic to save to SQLite via SQLAlchemy would go here
    return {"ok": True, "message": "Target registered."}

@app.get("/alerts")
async def get_alerts():
    # Logic to scan history for 20% drops
    return {"alerts": []}

async def polling_loop():
    """Background loop for staggered polling."""
    while True:
        print("[POLLER] Starting pass...")
        # 1. Fetch all targets
        # 2. For each: staggered await scraper.get_price()
        # 3. Apply 20% math vs Market Baseline
        # 4. If no baseline, set it from the first result
        await asyncio.sleep(300) # Placeholder for interval

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(polling_loop())
