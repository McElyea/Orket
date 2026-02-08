import asyncio
import re
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async

class PriceScraper:
    def __init__(self):
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
        ]

    def clean_price(self, price_str: str) -> float:
        """
        Robust price string cleaner. Handles currency symbols, 
        thousand separators, and decimal points.
        """
        if not price_str: return 0.0
        
        # 1. Remove everything except numbers, dots, and commas
        cleaned = re.sub(r'[^\d.,]', '', price_str)
        
        # 2. Identify regional format (e.g. 1.200,00 vs 1,200.00)
        if ',' in cleaned and '.' in cleaned:
            if cleaned.find('.') < cleaned.find(','):
                # Format: 1.200,00 (European)
                cleaned = cleaned.replace('.', '').replace(',', '.')
            else:
                # Format: 1,200.00 (US)
                cleaned = cleaned.replace(',', '')
        elif ',' in cleaned:
            # Format: 45,00 (likely decimal comma)
            # Check if comma is at the thousand position (simplified)
            parts = cleaned.split(',')
            if len(parts[-1]) == 3: # 1,000
                cleaned = cleaned.replace(',', '')
            else: # 45,00
                cleaned = cleaned.replace(',', '.')
                
        try:
            return float(cleaned)
        except ValueError:
            return 0.0

    async def get_price(self, url: str, selector_type: str, selector_value: str) -> dict:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(user_agent=self.user_agents[0])
            page = await context.new_page()
            await stealth_async(page)
            
            try:
                await page.goto(url, wait_until="networkidle", timeout=60000)
                
                element = None
                if selector_type == 'xpath':
                    element = await page.query_selector(f"xpath={selector_value}")
                elif selector_type == 'css':
                    element = await page.query_selector(selector_value)
                elif selector_type == 'id':
                    element = await page.query_selector(f"#{selector_value}")
                
                if element:
                    text = await element.inner_text()
                    price = self.clean_price(text)
                    return {"ok": True, "price": price, "raw": text}
                else:
                    return {"ok": False, "error": "Element not found"}
                    
            except Exception as e:
                return {"ok": False, "error": str(e)}
            finally:
                await browser.close()
