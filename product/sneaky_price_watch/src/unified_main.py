from controllers.price_alert_controller import PriceAlertController
import asyncio

async def main():
    controller = PriceAlertController()
    product_urls = ['http://example.com/product1', 'http://example.com/product2']
    
    # Setup alerts
    alerts = await controller.setup_alerts(product_urls, threshold=100.0)
    print("Alerts set up:", alerts)
    
    # Monitor prices
    monitor_alerts = await controller.monitor_prices(product_urls)
    print("Monitor alerts:", monitor_alerts)

if __name__ == "__main__":
    asyncio.run(main())