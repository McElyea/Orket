# Price Discovery and Alerting System

A local-first system for price discovery and alerting using FastAPI and Playwright.

## Features
- Price discovery using Playwright
- Alerting system with email notifications
- Stealth integration mode

## Endpoints
- `/api/price/{product_id}` - Get price for a product
- `/api/prices` - Get prices for multiple products
- `/api/alert` - Create an alert
- `/api/alerts` - Get all alerts
- `/api/stealth/status` - Get stealth mode status
- `/api/stealth/activate` - Activate stealth mode

## Installation
```bash
pip install -r requirements.txt
```

## Running
```bash
uvicorn main:app --reload
```