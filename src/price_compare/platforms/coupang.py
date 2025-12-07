"""Coupang platform implementation using never-primp HTTP client."""

import html
from typing import TYPE_CHECKING
from urllib.parse import quote

import never_primp as primp
from regex_rs import Regex

if TYPE_CHECKING:
    from never_primp.never_primp import IMPERSONATE

from price_compare.models import Product
from price_compare.platforms.base import BasePlatform

# Module-level compiled patterns ((?s) = DOTALL)
_PRODUCT_PATTERN = Regex(
    r'(?s)<li[^>]*class="search-product[^"]*"[^>]*'
    r'data-product-id="(\d+)"[^>]*>(.*?)</li>'
)
_NAME_PATTERN = Regex(r'<div[^>]*class="name"[^>]*>([^<]+)</div>')
_PRICE_PATTERN = Regex(r'class="price-value"[^>]*>([^<]+)<')


class CoupangPlatform(BasePlatform):
    """Coupang Taiwan shopping platform using never-primp for HTTP requests."""

    __slots__ = ("_client", "_impersonate", "_timeout")

    name = "coupang"
    _BASE_URL = "https://www.tw.coupang.com"
    _SEARCH_URL = "https://www.tw.coupang.com/np/search?q={}&sorter=LOWEST_PRICE_ASC&listSize=20"
    _PRODUCT_URL = "https://www.tw.coupang.com/vp/products/{}"

    def __init__(
        self,
        impersonate: "IMPERSONATE" = "chrome_142",
        timeout: float = 30.0,
    ) -> None:
        self._impersonate: IMPERSONATE = impersonate
        self._timeout = timeout
        self._client: primp.AsyncClient | None = None

    async def _get_client(self) -> primp.AsyncClient:
        """Get or create async HTTP client with browser impersonation."""
        if self._client is None:
            self._client = primp.AsyncClient(
                impersonate=self._impersonate,
                impersonate_os="windows",
                cookie_store=True,
                timeout=self._timeout,
                follow_redirects=True,
            )
        return self._client

    async def search(
        self,
        query: str,
        max_results: int = 50,
        required_keywords: list[str] | None = None,
    ) -> list[Product]:
        """
        Search products on Coupang using never-primp.

        Args:
            query: Search query string
            max_results: Maximum number of results to return
            required_keywords: Product name must contain ALL these keywords (case-insensitive)
        """
        client = await self._get_client()
        encoded_query = quote(query)
        url = self._SEARCH_URL.format(encoded_query)

        resp = await client.get(url)
        if resp.status_code != 200:
            return []

        # Unescape HTML entities
        content = html.unescape(resp.text)

        # Pre-process keywords for case-insensitive matching
        keywords_lower = [kw.lower() for kw in required_keywords] if required_keywords else None

        products: list[Product] = []
        seen_ids: set[str] = set()

        for caps in _PRODUCT_PATTERN.captures_iter(content):
            if len(products) >= max_results:
                break

            m_id, m_html = caps.get(1), caps.get(2)
            if not m_id or not m_html:
                continue

            product_id = m_id.matched_text
            if product_id in seen_ids:
                continue
            seen_ids.add(product_id)

            product_html = m_html.matched_text

            # Extract name from <div class="name">
            name_caps = _NAME_PATTERN.captures(product_html)
            if not name_caps:
                continue
            name_match = name_caps.get(1)
            if not name_match:
                continue
            name = name_match.matched_text.strip()
            if not name:
                continue

            # Filter by required keywords (all must match)
            if keywords_lower:
                name_lower = name.lower()
                if not all(kw in name_lower for kw in keywords_lower):
                    continue

            # Extract price from price-value class
            price_caps = _PRICE_PATTERN.captures(product_html)
            if not price_caps:
                continue
            price_match = price_caps.get(1)
            if not price_match:
                continue

            price_str = price_match.matched_text.replace(",", "")
            try:
                price = int(price_str)
            except ValueError:
                continue

            if price <= 0:
                continue

            products.append(
                Product(
                    name=name,
                    price=price,
                    url=self._PRODUCT_URL.format(product_id),
                    platform=self.name,
                )
            )

        return sorted(products, key=lambda p: p.price)[:max_results]

    async def close(self) -> None:
        """Close the HTTP client."""
        self._client = None
