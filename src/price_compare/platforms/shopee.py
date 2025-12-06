# """Shopee platform implementation using Playwright."""

# import asyncio
# from contextlib import suppress
# from urllib.parse import quote

# from playwright.async_api import async_playwright
# from regex_rs import Regex

# from price_compare.models import Product
# from price_compare.platforms.base import BasePlatform


# class ShopeePlatform(BasePlatform):
#     """Shopee shopping platform using Playwright for anti-bot bypass."""

#     __slots__ = ("_timeout",)

#     name = "shopee"
#     _SEARCH_URL = "https://shopee.tw/search?keyword={}&sortBy=price"
#     _PRODUCT_URL = "https://shopee.tw/product/{}/{}"

#     # Regex for extracting product data from page ((?s) = DOTALL)
#     _PRODUCT_PATTERN = Regex(r'(?s)"itemid":(\d+).*?"shopid":(\d+).*?"name":"([^"]+)".*?"price":(\d+)')
#     _NON_DIGIT_PATTERN = Regex(r"[^\d]")

#     def __init__(self, timeout: float = 30.0) -> None:
#         self._timeout = timeout

#     async def search(self, query: str, max_results: int = 50) -> list[Product]:
#         """Search products on Shopee using Playwright."""
#         encoded_query = quote(query)
#         url = self._SEARCH_URL.format(encoded_query)
#         products: list[Product] = []

#         async with async_playwright() as p:
#             browser = await p.chromium.launch(headless=True)
#             context = await browser.new_context(
#                 user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
#                 viewport={"width": 1920, "height": 1080},
#                 locale="zh-TW",
#             )
#             page = await context.new_page()

#             try:
#                 with suppress(Exception):
#                     await page.goto(url, wait_until="networkidle", timeout=self._timeout * 1000)
#                     await asyncio.sleep(2)  # Wait for dynamic content

#                     # Scroll to load more products
#                     await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
#                     await asyncio.sleep(1)

#                     # Get page content and extract data
#                     content = await page.content()

#                     # Try to find product data in the page
#                     seen_ids: set[str] = set()

#                     # Look for JSON data in scripts
#                     scripts = await page.evaluate("""
#                         () => {
#                             const items = [];
#                             document.querySelectorAll('[data-sqe="item"]').forEach(el => {
#                                 const link = el.querySelector('a');
#                                 const name = el.querySelector('[data-sqe="name"]')?.textContent;
#                                 const price = el.querySelector('[class*="price"]')?.textContent;
#                                 if (link && name) {
#                                     const href = link.getAttribute('href') || '';
#                                     const match = href.match(/product\\.(\\d+)\\.(\\d+)/);
#                                     if (match) {
#                                         items.push({
#                                             shopid: match[1],
#                                             itemid: match[2],
#                                             name: name,
#                                             price: price
#                                         });
#                                     }
#                                 }
#                             });
#                             return items;
#                         }
#                     """)

#                     for item in scripts[:max_results]:
#                         item_id = str(item.get("itemid", ""))
#                         if item_id in seen_ids:
#                             continue
#                         seen_ids.add(item_id)

#                         price_str = item.get("price", "0")
#                         price = self._parse_price(price_str)
#                         if price is None or price == 0:
#                             continue

#                         products.append(
#                             Product(
#                                 name=item.get("name", ""),
#                                 price=price,
#                                 url=self._PRODUCT_URL.format(item.get("shopid"), item_id),
#                                 platform=self.name,
#                             )
#                         )

#                     # Fallback: parse from network responses if DOM parsing failed
#                     if not products:
#                         products = self._parse_from_html(content, max_results)
#             finally:
#                 await browser.close()

#         return sorted(products, key=lambda p: p.price)[:max_results]

#     def _parse_price(self, price_str: str) -> int | None:
#         """Parse price string to integer."""
#         if not price_str:
#             return None
#         try:
#             # Remove currency symbols and commas
#             clean = self._NON_DIGIT_PATTERN.replace(str(price_str), "")
#             if not clean:
#                 return None
#             price = int(clean)
#             # Shopee prices are sometimes in cents
#             if price > 100000000:
#                 price //= 100000
#             return price
#         except (ValueError, AttributeError):
#             return None

#     def _parse_from_html(self, html: str, max_results: int) -> list[Product]:
#         """Fallback parser for HTML content."""
#         products: list[Product] = []
#         seen_ids: set[str] = set()

#         for caps in self._PRODUCT_PATTERN.captures_iter(html):
#             if len(products) >= max_results:
#                 break

#             m_item_id = caps.get(1)
#             m_shop_id = caps.get(2)
#             m_name = caps.get(3)
#             m_price = caps.get(4)
#             if not (m_item_id and m_shop_id and m_name and m_price):
#                 continue

#             item_id = m_item_id.matched_text
#             if item_id in seen_ids:
#                 continue

#             price = self._parse_price(m_price.matched_text)
#             if price is None:
#                 continue

#             seen_ids.add(item_id)
#             name = m_name.matched_text.replace("\\u0026", "&").replace("\\n", " ")
#             products.append(
#                 Product(
#                     name=name,
#                     price=price,
#                     url=self._PRODUCT_URL.format(m_shop_id.matched_text, item_id),
#                     platform=self.name,
#                 )
#             )

#         return products
