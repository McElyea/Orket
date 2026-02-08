import sqlite3

class PriceAccessor:
    def __init__(self):
        self.db_path = "prices.db"
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS prices (
                product_id TEXT PRIMARY KEY,
                price TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    def get_product_data(self, product_id: str):
        # Simulate fetching product data
        return {"id": product_id, "url": f"https://example.com/product/{product_id}"}

    def store_price(self, product_id: str, price: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO prices (product_id, price) VALUES (?, ?)",
            (product_id, price)
        )
        conn.commit()
        conn.close()