"""momo platform implementation."""

import asyncio
from urllib.parse import quote

import never_primp as primp
from regex_rs import Regex

from price_compare.models import Product
from price_compare.platforms.base import BasePlatform

# Regex for escaped JSON format (Next.js SSR data)
_JSON_PATTERN = Regex(
    r"(?s)goodsCode\\\":\\\"(\d+)\\\".*?"
    r"goodsName\\\":\\\"([^\\]+?)\\\".*?"
    r"SALE_PRICE\\\":\\\"(\d+)\\\""
)


class MomoPlatform(BasePlatform):
    """momo shopping platform."""

    __slots__ = ("_impersonate", "_timeout")

    name = "momo"
    _SEARCH_URL = "https://m.momoshop.com.tw/search.momo"
    _PRODUCT_URL = "https://www.momoshop.com.tw/goods/GoodsDetail.jsp?i_code={}"

    def __init__(
        self,
        impersonate: str | None = "chrome_142",
        timeout: float = 30.0,
    ) -> None:
        self._impersonate = impersonate
        self._timeout = timeout

    def _parse_price(self, price_str: str) -> int | None:
        """Parse price string to integer."""
        try:
            return int(price_str.replace(",", "").replace("$", ""))
        except (ValueError, AttributeError):
            return None

    def _parse_html(self, html: str) -> list[tuple[str, str, int]]:
        """Parse HTML to extract product data from escaped JSON."""
        results: list[tuple[str, str, int]] = []
        seen_ids: set[str] = set()

        for caps in _JSON_PATTERN.captures_iter(html):
            m1, m2, m3 = caps.get(1), caps.get(2), caps.get(3)
            if not m1 or not m2 or not m3:
                continue
            prod_id = m1.matched_text
            name = m2.matched_text
            price_str = m3.matched_text
            if prod_id in seen_ids:
                continue
            price = self._parse_price(price_str)
            if price is not None:
                seen_ids.add(prod_id)
                # Unescape JSON string
                clean_name = name.replace("\\\\", "\\").replace("\\/", "/")
                results.append((prod_id, clean_name, price))

        return results

    async def search(self, query: str, max_results: int = 50) -> list[Product]:
        """Search products on momo with concurrent page fetching."""
        encoded_query = quote(query)
        # First page usually has 30+ items, 2 pages max for price comparison
        pages_needed = min((max_results + 29) // 30, 2)

        async with primp.AsyncClient(
            impersonate=self._impersonate,
            impersonate_os="windows",
            timeout=self._timeout,
            http2_only=True,
            headers={
                "accept": "text/html,application/xhtml+xml",
                "accept-language": "zh-TW,zh;q=0.9",
            },
        ) as client:
            # Build URLs for all pages
            urls = [
                f"{self._SEARCH_URL}?searchKeyword={encoded_query}&searchType=1&curPage={p}"
                for p in range(1, pages_needed + 1)
            ]

            # Fetch all pages concurrently
            tasks = [client.get(url) for url in urls]
            responses = await asyncio.gather(*tasks, return_exceptions=True)

            # Parse all responses
            products: list[Product] = []
            seen_ids: set[str] = set()

            for resp in responses:
                if isinstance(resp, BaseException) or resp.status_code != 200:
                    continue

                for prod_id, name, price in self._parse_html(resp.text):
                    if prod_id in seen_ids or len(products) >= max_results:
                        continue
                    seen_ids.add(prod_id)
                    products.append(
                        Product(
                            name=name,
                            price=price,
                            url=self._PRODUCT_URL.format(prod_id),
                            platform=self.name,
                        )
                    )

        return sorted(products, key=lambda p: p.price)[:max_results]
