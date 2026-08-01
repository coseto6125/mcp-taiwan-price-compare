"""Coupang platform implementation."""

import html
import re
from collections.abc import Iterator
from contextlib import suppress
from typing import TYPE_CHECKING
from urllib.parse import quote

import never_primp as primp

if TYPE_CHECKING:
    from never_primp import IMPERSONATE

from price_compare.platforms.base import BasePlatform, Candidate

# Search results are server-rendered CSS modules: class names keep a stable prefix
# and a build-specific hash suffix, so every pattern matches on the prefix only.
_PRODUCT_DELIMITER = '<li class="ProductUnit_productUnit__'
_ID_PATTERN = re.compile(r'data-id="(\d+)"')
_LINK_PATTERN = re.compile(r'href="(/products/[^"?]+)\?[^"]*itemId=(\d+)')
_NAME_PATTERN = re.compile(r'<div class="ProductUnit_productNameV2__[^"]*">([^<]+)</div>')
# Sale price sits in a <span translate="no">; the struck-through list price is a bare <del>.
_PRICE_PATTERN = re.compile(r'<span translate="no">\$([\d,]+)</span>')


class CoupangPlatform(BasePlatform[str]):
    """Coupang Taiwan shopping platform."""

    __slots__ = ("_impersonate", "_timeout")

    name = "coupang"
    # sorter=salePriceAsc is the live low-price sort; the older LOWEST_PRICE_ASC is a
    # dead parameter that returns the same order as the relevance default.
    _SEARCH_URL = "https://www.tw.coupang.com/np/search?q={}&sorter=salePriceAsc&listSize=60"
    _PRODUCT_URL = "https://www.tw.coupang.com{}?itemId={}&vendorItemId={}"

    def __init__(self, impersonate: "IMPERSONATE | None" = "chrome_142", timeout: float = 30.0) -> None:
        self._impersonate = impersonate
        self._timeout = timeout

    async def _fetch(self, query: str, max_results: int, *, include_auction: bool = False) -> str | None:
        """Request the search page and return its HTML."""
        async with primp.AsyncClient(
            impersonate=self._impersonate,
            impersonate_os="windows",
            timeout=self._timeout,
            follow_redirects=True,
        ) as client:
            with suppress(Exception):
                resp = await client.get(self._SEARCH_URL.format(quote(query)))
                if resp.status_code == 200:
                    return resp.text
        return None

    def _extract(self, payload: str) -> Iterator[Candidate]:
        """
        Read product blocks out of the search HTML.

        Each product is one <li>; splitting on its opening tag avoids the nested <li>
        elements (rating, badges) that a non-greedy </li> match would trip on.
        """
        for block in payload.split(_PRODUCT_DELIMITER)[1:]:
            vendor_item_id = _ID_PATTERN.search(block)
            name = _NAME_PATTERN.search(block)
            price = _PRICE_PATTERN.search(block)
            # Product path and itemId live in the same href.
            link = _LINK_PATTERN.search(block)
            if not (vendor_item_id and name and price and link):
                continue

            # Unescape the captured values, never the page: the href holds &amp;
            # separators and a name may hold &quot;, both of which corrupt matching.
            yield Candidate(
                id=vendor_item_id[1],
                name=html.unescape(name[1]),
                price=price[1],
                url=self._PRODUCT_URL.format(html.unescape(link[1]), link[2], vendor_item_id[1]),
            )
