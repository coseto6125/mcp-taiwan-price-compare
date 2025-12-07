"""Coupang platform implementation."""

import html
from contextlib import suppress
from typing import TYPE_CHECKING
from urllib.parse import quote

import never_primp as primp
from regex_rs import Regex

if TYPE_CHECKING:
    from never_primp import IMPERSONATE

from price_compare.models import Product
from price_compare.platforms.base import BasePlatform
from price_compare.utils import KeywordGroups, matches_keywords, prepare_keyword_groups

# Module-level compiled patterns ((?s) = DOTALL)
_PRODUCT_PATTERN = Regex(
    r'(?s)<li[^>]*class="search-product[^"]*"[^>]*'
    r'data-product-id="(\d+)"[^>]*>(.*?)</li>'
)
_NAME_PATTERN = Regex(r'<div[^>]*class="name"[^>]*>([^<]+)</div>')
_PRICE_PATTERN = Regex(r'class="price-value"[^>]*>([^<]+)<')


class CoupangPlatform(BasePlatform):
    """Coupang Taiwan shopping platform."""

    __slots__ = ("_impersonate", "_timeout")

    name = "coupang"
    _SEARCH_URL = "https://www.tw.coupang.com/np/search?q={}&sorter=LOWEST_PRICE_ASC&listSize=60"
    _PRODUCT_URL = "https://www.tw.coupang.com/vp/products/{}"

    def __init__(self, impersonate: "IMPERSONATE | None" = "chrome_142", timeout: float = 30.0) -> None:
        self._impersonate = impersonate
        self._timeout = timeout

    async def search(
        self,
        query: str,
        max_results: int = 100,
        min_price: int = 0,
        max_price: int = 0,
        require_words: KeywordGroups = None,
        **_: object,
    ) -> list[Product]:
        """Search products on Coupang."""
        url = self._SEARCH_URL.format(quote(query))
        prepared_keywords = prepare_keyword_groups(require_words)

        async with primp.AsyncClient(
            impersonate=self._impersonate,
            impersonate_os="windows",
            timeout=self._timeout,
            follow_redirects=True,
        ) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return []

            return self._parse_products(html.unescape(resp.text), max_results, min_price, max_price, prepared_keywords)

    def _parse_products(
        self,
        content: str,
        max_results: int,
        min_price: int,
        max_price: int,
        prepared_keywords: tuple[tuple[str, ...], ...] | None,
    ) -> list[Product]:
        """Parse HTML content into Product list."""
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

            product_html = m_html.matched_text

            # Extract name (walrus chain)
            if not (name_caps := _NAME_PATTERN.captures(product_html)):
                continue
            if not (name_match := name_caps.get(1)):
                continue
            if not (name := name_match.matched_text.strip()):
                continue
            if not matches_keywords(name.lower(), prepared_keywords):
                continue

            # Extract and validate price
            if not (price_caps := _PRICE_PATTERN.captures(product_html)):
                continue
            if not (price_match := price_caps.get(1)):
                continue

            with suppress(ValueError):
                price = int(price_match.matched_text.replace(",", ""))

                # Combined price filter
                if price <= 0 or (min_price and price < min_price) or (max_price and price > max_price):
                    continue

                seen_ids.add(product_id)
                products.append(Product(name=name, price=price, url=self._PRODUCT_URL.format(product_id), platform=self.name))

        return products
