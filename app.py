#!/usr/bin/env python3
"""
JYSK Stock & Price Monitoring System
Monitors JYSK Morocco product stock levels and price changes
"""

import asyncio
import sqlite3
import yaml
import csv
import re
import time
import logging
import argparse
import unicodedata
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Tuple
from dataclasses import dataclass

from playwright.async_api import async_playwright, Page
import requests

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class ProductConfig:
    jumia_sku: str
    jysk_url: str
    reference_price: float
    click_text: Optional[str] = None
    row_selector: Optional[str] = None


@dataclass
class StoreStock:
    store_name: str
    qty: Optional[int]
    status: str  # in_stock, out_of_stock, unknown
    raw_text: Optional[str] = None


@dataclass
class PriceInfo:
    current_price: float
    original_price: Optional[float] = None
    is_on_sale: bool = False


# ----------------------
# Helpers (NEW)
# ----------------------
def _norm(s: str) -> str:
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower().strip()

MAGASIN_RX = re.compile(r"\b\d+\s+magasin(s)?\b", re.I)


class JYSKMonitor:
    def __init__(self, config_path: str = "config.yaml"):
        self.config = self.load_config(config_path)
        self.db_path = "jysk_stock.db"
        self.init_database()
        
    def load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file"""
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def init_database(self):
        """Initialize SQLite database with required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Products table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                jumia_sku TEXT UNIQUE NOT NULL,
                jysk_url TEXT NOT NULL,
                reference_price REAL NOT NULL,
                active INTEGER DEFAULT 1,
                click_text TEXT,
                row_selector TEXT
            )
        ''')
        
        # Stock snapshots table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                store_name TEXT NOT NULL,
                qty INTEGER,
                status TEXT NOT NULL,
                price REAL,
                original_price REAL,
                is_on_sale INTEGER DEFAULT 0,
                fetched_at INTEGER NOT NULL,
                raw TEXT,
                FOREIGN KEY (product_id) REFERENCES products (id)
            )
        ''')
        
        # Alerts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                store_name TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                prev_value TEXT,
                curr_value TEXT,
                sent_at INTEGER NOT NULL,
                channel TEXT NOT NULL,
                FOREIGN KEY (product_id) REFERENCES products (id)
            )
        ''')
        
        # Create indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_snapshots_product_store_time ON snapshots(product_id, store_name, fetched_at DESC)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_alerts_product_store_time ON alerts(product_id, store_name, sent_at DESC)')
        
        conn.commit()
        conn.close()
    
    async def scrape_product_info(self, page: Page, product: ProductConfig) -> Tuple[List[StoreStock], PriceInfo]:
        """Scrape stock and price information for a single product"""
        logger.info(f"Scraping product: {product.jumia_sku}")
        
        try:
            # Navigate to product page
            await page.goto(product.jysk_url, wait_until='networkidle', timeout=self.config['timeout_ms'])
            await asyncio.sleep(2)  # let hydration/observers settle
            
            # Extract price information
            price_info = await self.extract_price(page)
            logger.info(f"Found price: {price_info.current_price} DH")
            
            # Open the list of stores by clicking 'X magasins' (the real actionable control)
            drawer_opened = await self.open_store_drawer(page)
            if not drawer_opened:
                logger.warning(f"Could not open store drawer for {product.jumia_sku}")
                return [], price_info
            
            # Ensure results are actually rendered
            await asyncio.sleep(2)
            
            # Force city to Casablanca & ensure list is populated (handles fresh/headless sessions)
            await self.set_city_to_casablanca(page)
            
            # Extract stock information for target stores (robust to virtualization)
            stock_info = await self.extract_stock_info(page)
            return stock_info, price_info
            
        except Exception as e:
            logger.error(f"Error scraping {product.jumia_sku}: {str(e)}")
            return [], PriceInfo(0.0)
    
    async def extract_price(self, page: Page) -> PriceInfo:
        """Extract price information from product page"""
        try:
            # Try to find promotional price first
            promo_price_element = await page.query_selector('.ssr-product-price.offerprice .ssr-product-price__value')
            if promo_price_element:
                promo_text = await promo_price_element.text_content()
                promo_price = float(re.search(r'(\d+(?:,\d+)*(?:\.\d+)?)', promo_text.replace(',', '.')).group(1))
                
                # Original price
                original_price_element = await page.query_selector('.ssr-product-price.normalprice .ssr-product-price__value')
                original_price = None
                if original_price_element:
                    original_text = await original_price_element.text_content()
                    original_price = float(re.search(r'(\d+(?:,\d+)*(?:\.\d+)?)', original_text.replace(',', '.')).group(1))
                
                return PriceInfo(promo_price, original_price, True)
            
            # Regular price
            price_element = await page.query_selector('.ssr-product-price.normalprice .ssr-product-price__value, .ssr-product-price__value')
            if price_element:
                price_text = await price_element.text_content()
                price = float(re.search(r'(\d+(?:,\d+)*(?:\.\d+)?)', price_text.replace(',', '.')).group(1))
                return PriceInfo(price)
            
            logger.warning("Could not find price information")
            return PriceInfo(0.0)
            
        except Exception as e:
            logger.error(f"Error extracting price: {str(e)}")
            return PriceInfo(0.0)

    # ----------------------
    # Drawer opening (NEW)
    # ----------------------
    async def open_store_drawer(self, page: Page) -> bool:
        """
        Opens the store availability drawer by clicking the 'X magasins' button
        inside the 'Click & Collect' block. Returns True if the drawer is visible.
        """
        # Scope to the Click & Collect card to avoid false positives
        cc_section = page.locator(
            "section:has-text('Click & Collect'), "
            "div:has(h2:has-text('Click & Collect')), "
            "div:has-text('Click & Collect')"
        ).first
        try:
            await cc_section.scroll_into_view_if_needed()
        except:
            pass

        # Prefer role-based selector with regex name, then class + text
        btn = cc_section.get_by_role("button", name=MAGASIN_RX).first
        if not await btn.count():
            btn = cc_section.locator("button.btn-link").filter(has_text=re.compile(r"magasin", re.I)).first
        if not await btn.count():
            btn = cc_section.locator("button").filter(has_text=MAGASIN_RX).first

        if not await btn.count():
            logger.warning("Could not locate 'X magasins' button inside Click & Collect section")
            return False

        try:
            await btn.scroll_into_view_if_needed()
            await btn.click(timeout=2500)
        except Exception:
            # Fallback JS click if overlay swallows events
            try:
                el_handle = await btn.element_handle()
                if el_handle:
                    await page.evaluate("(el)=>{el.click();}", el_handle)
            except:
                pass

        # Wait for drawer / modal / list to appear
        drawer = page.locator(
            "[role='dialog'], .modal, .drawer, "
            ".store-selector, [data-testid*='store-selector'], "
            ".store-list, [data-testid*='store-list']"
        ).first
        try:
            await drawer.wait_for(state="visible", timeout=4000)
            logger.info("Successfully opened drawer with: X magasins")
            return True
        except:
            return False

    # ----------------------
    # City selection (NEW)
    # ----------------------
    async def set_city_to_casablanca(self, page: Page):
        """Type 'Casablanca' into the drawer search/city input to force the correct store list."""
        # Common search inputs within selector panels
        inputs = page.locator(
            "input[placeholder*='ville'], input[placeholder*='city'], input[type='search'], "
            "input[aria-label*='ville'], input[aria-label*='City']"
        )
        if await inputs.count() == 0:
            # Sometimes a button opens a sub-panel to choose the city
            try:
                await page.locator("button:has-text('Changer de magasin'), button:has-text('Sélectionnez votre magasin')").first.click(timeout=1500)
            except:
                pass
            inputs = page.locator("input[type='search']")

        if await inputs.count() > 0:
            el = inputs.first
            await el.fill("")
            await el.type("Casablanca", delay=35)
            await page.wait_for_timeout(800)
            await page.wait_for_load_state("networkidle")
            # Wait for at least one row to show up
            try:
                await page.wait_for_selector(".store-list >> .store, .shop, li, [role='option']", timeout=4000)
            except:
                pass

    # ----------------------
    # Store discovery (NEW)
    # ----------------------
    async def find_store_row(self, page: Page, target_name: str):
        target_norm = _norm(target_name)
        container = page.locator(".store-list, [data-testid*='store-list'], [role='listbox'], .drawer")
        if await container.count() == 0:
            container = page.locator("body")

        # Scroll to trigger virtualization, up to ~12 "screens"
        for _ in range(12):
            rows = container.locator(".store, .shop, li, [role='option'], [data-testid*='store']")
            n = await rows.count()
            for i in range(n):
                row = rows.nth(i)
                try:
                    txt = _norm(await row.inner_text())
                except:
                    continue
                if target_norm in txt:
                    await row.scroll_into_view_if_needed()
                    return row
            # load more
            try:
                await container.evaluate("(el)=>{el.scrollBy(0, el.clientHeight || 600)}")
            except:
                await page.keyboard.press("PageDown")
            await page.wait_for_timeout(350)
        return None

    async def extract_qty_from_row(self, row) -> Tuple[Optional[int], str]:
        """Try several patterns to get quantity and raw text from a store row."""
        # explicit numbers in common sub-elements
        for sel in [".qty, [data-testid*='qty'], .badge", ".stock, .availability", "span, div"]:
            try:
                els = row.locator(sel)
                count = await els.count()
            except:
                continue
            for i in range(min(count, 8)):
                try:
                    t = (await els.nth(i).inner_text() or "").strip()
                except:
                    continue
                m = re.search(r"(\d+)", t)
                if m:
                    return int(m.group(1)), t

        # textual status
        try:
            txt = (await row.inner_text() or "").lower()
        except:
            txt = ""
        if any(k in txt for k in ["épuisé", "rupture", "pas de stock", "out of stock"]):
            return 0, txt
        if any(k in txt for k in ["en stock", "disponible", "available"]):
            return 1, txt  # minimum 1 if not specified
        return None, txt

    async def extract_stock_info(self, page: Page) -> List[StoreStock]:
        """Extract stock information for configured stores from the opened drawer."""
        stock_info: List[StoreStock] = []
        target_stores = [store['name'] for store in self.config['stores']]

        # Make sure some list-like content is visible
        try:
            await page.wait_for_selector('[role="dialog"], .store-list, .drawer', timeout=5000)
        except:
            pass

        for store_name in target_stores:
            try:
                row = await self.find_store_row(page, store_name)
                if not row:
                    logger.warning(f"Could not find store: {store_name}")
                    # debug evidence
                    ts = int(time.time())
                    await page.screenshot(path=f"debug_{ts}_{_norm(store_name)[:20]}.png", full_page=True)
                    html = await page.content()
                    Path(f"debug_{ts}_{_norm(store_name)[:20]}.html").write_text(html, encoding="utf-8")
                    stock_info.append(StoreStock(store_name, None, "unknown"))
                    continue

                qty, raw = await self.extract_qty_from_row(row)
                status = "unknown"
                if qty is not None:
                    status = "in_stock" if qty > 0 else "out_of_stock"
                stock_info.append(StoreStock(store_name, qty, status, raw))
                logger.info(f"Found stock for {store_name}: {qty} pieces ({status})")
            except Exception as e:
                logger.error(f"Error extracting stock for {store_name}: {str(e)}")
                stock_info.append(StoreStock(store_name, None, "unknown"))

        return stock_info
    
    def save_snapshot(self, product_id: int, stock_info: List[StoreStock], price_info: PriceInfo):
        """Save stock and price snapshot to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        timestamp = int(time.time())
        
        for stock in stock_info:
            cursor.execute('''
                INSERT INTO snapshots (product_id, store_name, qty, status, price, original_price, is_on_sale, fetched_at, raw)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (product_id, stock.store_name, stock.qty, stock.status, 
                  price_info.current_price, price_info.original_price, 
                  price_info.is_on_sale, timestamp, stock.raw_text))
        
        conn.commit()
        conn.close()
    
    def check_alerts(self, product_id: int, stock_info: List[StoreStock], price_info: PriceInfo, reference_price: float, jumia_sku: str, jysk_url: str):
        """Check if any alerts should be triggered"""
        
        # Price change
        if price_info.current_price > 0 and abs(price_info.current_price - reference_price) >= 0.01:
            if self.should_send_alert(product_id, 'price_change', 'price_change'):
                self.send_price_change_alert(jumia_sku, jysk_url, reference_price, price_info.current_price)
                self.record_alert(product_id, 'price_change', 'price_change', str(reference_price), str(price_info.current_price))
        
        # Stock alerts
        stock_below_limit = False
        for stock in stock_info:
            store_threshold = next((s['stock_threshold'] for s in self.config['stores'] if s['name'] == stock.store_name), None)
            if store_threshold and stock.qty is not None and stock.qty < store_threshold:
                stock_below_limit = True
        
        if stock_below_limit and self.should_send_alert(product_id, 'stock', 'stock_low'):
            self.send_stock_alert(jumia_sku, jysk_url, stock_info)
            self.record_alert(product_id, 'stock', 'stock_low', '', '')
    
    def should_send_alert(self, product_id: int, store_name: str, alert_type: str) -> bool:
        """Check if we should send an alert based on cooldown period"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        min_hours = self.config['alerts']['min_hours_between_same_alert']
        cutoff_time = int(time.time()) - (min_hours * 3600)
        
        cursor.execute('''
            SELECT COUNT(*) FROM alerts 
            WHERE product_id = ? AND store_name = ? AND alert_type = ? AND sent_at > ?
        ''', (product_id, store_name, alert_type, cutoff_time))
        
        count = cursor.fetchone()[0]
        conn.close()
        
        return count == 0
    
    def record_alert(self, product_id: int, store_name: str, alert_type: str, prev_value: str, curr_value: str):
        """Record that an alert was sent"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO alerts (product_id, store_name, alert_type, prev_value, curr_value, sent_at, channel)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (product_id, store_name, alert_type, prev_value, curr_value, int(time.time()), 'telegram'))
        
        conn.commit()
        conn.close()
    
    def send_stock_alert(self, jumia_sku: str, jysk_url: str, stock_info: List[StoreStock]):
        """Send stock alert via Telegram with both stores info"""
        viva_park_stock = "N/A"
        aeria_mall_stock = "N/A"
        
        for stock in stock_info:
            if "Viva Park" in stock.store_name:
                viva_park_stock = f"{stock.qty} pieces" if stock.qty is not None else "Out of stock"
            elif "Aeria Mall" in stock.store_name:
                aeria_mall_stock = f"{stock.qty} pieces" if stock.qty is not None else "Out of stock"
        
        message = f"""🚨 [JYSK STOCK ALERT] 🚨
SKU: {jumia_sku}
Link: {jysk_url}

Current Stock:
📍 JYSK Viva Park: {viva_park_stock} (limit: 6)
📍 JYSK Aeria Mall: {aeria_mall_stock} (limit: 8)

⚠️ STOCK BELOW LIMITS
Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}"""
        
        self.send_telegram_message(message)
    
    def send_price_change_alert(self, jumia_sku: str, jysk_url: str, old_price: float, new_price: float):
        """Send price change alert via Telegram"""
        direction = "📈 HIGHER" if new_price > old_price else "📉 LOWER"
        change_amount = abs(new_price - old_price)
        
        message = f"""{direction.split()[0]} [JYSK PRICE ALERT] {direction.split()[0]}
SKU: {jumia_sku}
Link: {jysk_url}

Price Change:
Previous: {old_price:.2f} DH
Current: {new_price:.2f} DH
Difference: {change_amount:.2f} DH ({direction})

Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}"""
        
        self.send_telegram_message(message)
    
    def send_telegram_message(self, message: str):
        """Send message via Telegram Bot API"""
        if not self.config['alerts']['telegram']['enabled']:
            logger.info("Telegram alerts disabled")
            return
        
        bot_token = self.config['alerts']['telegram']['bot_token']
        chat_id = self.config['alerts']['telegram']['chat_id']
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': message
        }
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                logger.info("Telegram alert sent successfully")
            else:
                logger.error(f"Failed to send Telegram alert: {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"Error sending Telegram alert: {str(e)}")
    
    async def run_monitoring_cycle(self):
        """Run a complete monitoring cycle for all active products"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT id, jumia_sku, jysk_url, reference_price, click_text, row_selector FROM products WHERE active = 1')
        products = cursor.fetchall()
        conn.close()
        
        if not products:
            logger.info("No active products found")
            return
        
        logger.info(f"Found {len(products)} active products to monitor")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.config['headless'])
            # Seed Casablanca locale/UA if you want:
            page = await browser.new_page()
            
            for product_data in products:
                product_id, jumia_sku, jysk_url, reference_price, click_text, row_selector = product_data
                
                product = ProductConfig(jumia_sku, jysk_url, reference_price, click_text, row_selector)
                
                try:
                    stock_info, price_info = await self.scrape_product_info(page, product)
                    
                    # Save data even if empty (for tracking)
                    self.save_snapshot(product_id, stock_info, price_info)
                    
                    # Check for alerts
                    if stock_info or price_info.current_price > 0:
                        self.check_alerts(product_id, stock_info, price_info, reference_price, jumia_sku, jysk_url)
                    
                    # Delay between products
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    logger.error(f"Error processing product {jumia_sku}: {str(e)}")
            
            await browser.close()
        
        logger.info("Monitoring cycle completed")
    
    def import_products_from_csv(self, csv_path: str):
        """Import products from CSV file"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        imported_count = 0
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                cursor.execute('''
                    INSERT OR REPLACE INTO products (jumia_sku, jysk_url, reference_price, click_text, row_selector)
                    VALUES (?, ?, ?, ?, ?)
                ''', (row['jumia_sku'], row['jysk_url'], float(row['reference_price']), 
                      row.get('click_text'), row.get('row_selector')))
                imported_count += 1
        
        conn.commit()
        conn.close()
        logger.info(f"Successfully imported {imported_count} products from {csv_path}")
    
    def export_latest_snapshots_to_csv(self, csv_path: str):
        """Export latest snapshots to CSV file"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT p.jumia_sku, p.jysk_url, p.reference_price, s.store_name, s.qty, s.status, s.price, s.fetched_at
            FROM products p
            LEFT JOIN snapshots s ON p.id = s.product_id
            ORDER BY p.jumia_sku, s.store_name
        ''')
        
        results = cursor.fetchall()
        conn.close()
        
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['jumia_sku', 'jysk_url', 'reference_price', 'store_name', 'current_stock', 'status', 'current_price', 'last_checked'])
            writer.writerows(results)
        
        logger.info(f"Latest snapshots exported to {csv_path}")


def main():
    parser = argparse.ArgumentParser(description='JYSK Stock & Price Monitor')
    parser.add_argument('command', nargs='?', choices=['run-once', 'import-csv', 'export-csv'], help='Command to execute')
    parser.add_argument('--every', choices=['4d', '7d'], help='Run monitoring loop every X days')
    parser.add_argument('file', nargs='?', help='CSV file path for import/export')
    parser.add_argument('--config', default='config.yaml', help='Config file path')
    
    args = parser.parse_args()
    
    monitor = JYSKMonitor(args.config)
    
    if args.command == 'import-csv' and args.file:
        monitor.import_products_from_csv(args.file)
    elif args.command == 'export-csv' and args.file:
        monitor.export_latest_snapshots_to_csv(args.file)
    elif args.command == 'run-once':
        asyncio.run(monitor.run_monitoring_cycle())
    elif args.every:
        # Loop mode
        days = int(args.every[:-1])
        interval = days * 24 * 3600  # seconds
        
        logger.info(f"Starting monitoring loop every {days} days")
        while True:
            try:
                asyncio.run(monitor.run_monitoring_cycle())
                logger.info(f"Monitoring cycle complete. Sleeping for {days} days...")
                time.sleep(interval)
            except KeyboardInterrupt:
                logger.info("Monitoring stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {str(e)}")
                time.sleep(3600)  # Sleep 1 hour before retry
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
