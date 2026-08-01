"""Coupang platform implementation."""

import html
import re
from contextlib import suppress
from typing import TYPE_CHECKING
from urllib.parse import quote

import never_primp as primp

if TYPE_CHECKING:
    from never_primp import IMPERSONATE

from price_compare.models import Product
from price_compare.platforms.base import BasePlatform
from price_compare.utils import KeywordGroups, matches_keywords, prepare_keyword_groups

# Search results are server-rendered CSS modules: class names keep a stable prefix
# and a build-specific hash suffix, so every pattern matches on the prefix only.
_PRODUCT_DELIMITER = '<li class="ProductUnit_productUnit__'
_ID_PATTERN = re.compile(r'data-id="(\d+)"')
_LINK_PATTERN = re.compile(r'href="(/products/[^"?]+)\?[^"]*itemId=(\d+)')
_NAME_PATTERN = re.compile(r'<div class="ProductUnit_productNameV2__[^"]*">([^<]+)</div>')
# Sale price sits in a <span translate="no">; the struck-through list price is a bare <del>.
_PRICE_PATTERN = re.compile(r'<span translate="no">\$([\d,]+)</span>')


class CoupangPlatform(BasePlatform):
    """Coupang Taiwan shopping platform."""

    __slots__ = ("_impersonate", "_timeout")

    name = "coupang"
    _SEARCH_URL = "https://www.tw.coupang.com/np/search?q={}&sorter=salePriceAsc&listSize=60"
    _PRODUCT_URL = "https://www.tw.coupang.com{}?itemId={}&vendorItemId={}"

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

            return self._parse_products(resp.text, max_results, min_price, max_price, prepared_keywords)

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

        # Each product is one <li>; splitting on its opening tag avoids the nested
        # <li> elements (rating, badges) that a non-greedy </li> match would trip on.
        for block in content.split(_PRODUCT_DELIMITER)[1:]:
            if len(products) >= max_results:
                break

            if not (id_match := _ID_PATTERN.search(block)) or (vendor_item_id := id_match[1]) in seen_ids:
                continue
            # Unescape the captured value, never the page: the href holds &amp; separators
            # and a name may hold &quot;, both of which corrupt matching if resolved first.
            if not (name_match := _NAME_PATTERN.search(block)) or not (name := html.unescape(name_match[1]).strip()):
                continue
            if not matches_keywords(name.lower(), prepared_keywords):
                continue
            if not (price_match := _PRICE_PATTERN.search(block)):
                continue

            # Product path and itemId live in the same href
            if not (link_match := _LINK_PATTERN.search(block)):
                continue

            with suppress(ValueError):
                price = int(price_match[1].replace(",", ""))

                # Combined price filter
                if price <= 0 or (min_price and price < min_price) or (max_price and price > max_price):
                    continue

                seen_ids.add(vendor_item_id)
                products.append(
                    Product(
                        name=name,
                        price=price,
                        url=self._PRODUCT_URL.format(html.unescape(link_match[1]), link_match[2], vendor_item_id),
                        platform=self.name,
                    )
                )

        return products
