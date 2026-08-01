"""Uni-Prosperity (萬家福線上購物) platform implementation."""

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

# Salesforce Commerce Cloud tiles: every field is an attribute on the anchor that
# opens the tile, so matching the opening tag alone is enough. The same product also
# appears in a sibling favourite widget carrying data-likepid, which this pattern skips.
_TILE_PATTERN = re.compile(r'<a class="gtm-product-alink"([^>]*)>')
_PID_PATTERN = re.compile(r'data-pid="([^"]+)"')
_PRICE_PATTERN = re.compile(r'data-price="([\d.]+)"')
_NAME_PATTERN = re.compile(r'data-name="([^"]*)"')
_HREF_PATTERN = re.compile(r'href="([^"]+)"')
_UNAVAILABLE = 'data-ifavailable="false"'


class UniProsperityPlatform(BasePlatform):
    """Uni-Prosperity (萬家福線上購物) platform."""

    __slots__ = ("_impersonate", "_timeout")

    name = "uniprosperity"
    _SITE_URL = "https://online.uni-prosperity.com.tw"
    # The storefront's own grid endpoint returns the full result set as a bare product
    # list, roughly 15x smaller than the rendered search page it backs.
    _SEARCH_URL = (
        "https://online.uni-prosperity.com.tw"
        "/on/demandware.store/Sites-Uniprosperity-Site/default/Search-UpdateGrid?q=q%3D{}"
    )

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
        """Search products on Uni-Prosperity."""
        prepared_keywords = prepare_keyword_groups(require_words)

        async with primp.AsyncClient(
            impersonate=self._impersonate,
            impersonate_os="windows",
            timeout=self._timeout,
            follow_redirects=True,
        ) as client:
            resp = await client.get(self._SEARCH_URL.format(quote(query)))
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
        """Parse tile attributes into a price-ascending Product list."""
        products: list[Product] = []
        seen_ids: set[str] = set()

        for match in _TILE_PATTERN.finditer(content):
            attrs = match[1]

            if not (pid_match := _PID_PATTERN.search(attrs)) or (product_id := pid_match[1]) in seen_ids:
                continue
            if _UNAVAILABLE in attrs:
                continue
            # Unescape the captured value, never the page: a name holding &quot; would
            # otherwise become a bare quote and close the attribute match early, truncating it.
            if not (name_match := _NAME_PATTERN.search(attrs)) or not (name := html.unescape(name_match[1]).strip()):
                continue
            if not matches_keywords(name.lower(), prepared_keywords):
                continue
            if not (price_match := _PRICE_PATTERN.search(attrs)) or not (href_match := _HREF_PATTERN.search(attrs)):
                continue

            with suppress(ValueError):
                price = int(float(price_match[1]))

                if price <= 0 or (min_price and price < min_price) or (max_price and price > max_price):
                    continue

                seen_ids.add(product_id)
                products.append(
                    Product(name=name, price=price, url=f"{self._SITE_URL}{html.unescape(href_match[1])}", platform=self.name)
                )

        # The endpoint returns the whole result set and offers no price sort of its own,
        # so sorting here yields the genuinely cheapest matches rather than a page of them.
        products.sort(key=lambda p: p.price)
        return products[:max_results]
