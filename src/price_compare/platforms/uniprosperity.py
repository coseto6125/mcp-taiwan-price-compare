"""Uni-Prosperity (萬家福線上購物) platform implementation."""

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

# Salesforce Commerce Cloud tiles: every field is an attribute on the anchor that
# opens the tile, so matching the opening tag alone is enough. The same product also
# appears in a sibling favourite widget carrying data-likepid, which this pattern skips.
_TILE_DELIMITER = '<a class="gtm-product-alink"'
_TILE_PATTERN = re.compile(rf"{re.escape(_TILE_DELIMITER)}([^>]*)>")
_PID_PATTERN = re.compile(r'data-pid="([^"]+)"')
_PRICE_PATTERN = re.compile(r'data-price="([\d.]+)"')
_NAME_PATTERN = re.compile(r'data-name="([^"]*)"')
_HREF_PATTERN = re.compile(r'href="([^"]+)"')
_UNAVAILABLE = 'data-ifavailable="false"'


class UniProsperityPlatform(BasePlatform[str]):
    """Uni-Prosperity (萬家福線上購物) platform."""

    __slots__ = ("_impersonate", "_timeout")

    name = "uniprosperity"
    _SITE_URL = "https://online.uni-prosperity.com.tw"
    # The storefront's own grid endpoint returns the full result set as a bare product
    # list, roughly 15x smaller than the rendered search page it backs. It offers no
    # price ordering, so the pipeline sorts what comes back.
    _SEARCH_URL = "https://online.uni-prosperity.com.tw/on/demandware.store/Sites-Uniprosperity-Site/default/Search-UpdateGrid?q=q%3D{}"

    def __init__(self, impersonate: "IMPERSONATE | None" = "chrome_142", timeout: float = 30.0) -> None:
        self._impersonate = impersonate
        self._timeout = timeout

    async def _fetch(self, query: str, max_results: int, *, include_auction: bool = False) -> str | None:
        """Request the grid endpoint and return its HTML."""
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
        """Read product tiles out of the grid HTML."""
        for match in _TILE_PATTERN.finditer(payload):
            attrs = match[1]
            if _UNAVAILABLE in attrs:
                continue

            pid, name = _PID_PATTERN.search(attrs), _NAME_PATTERN.search(attrs)
            price, href = _PRICE_PATTERN.search(attrs), _HREF_PATTERN.search(attrs)
            if not (pid and name and price and href):
                continue

            # Unescape the captured values, never the page: a name holding &quot; would
            # otherwise become a bare quote and close the attribute match early.
            yield Candidate(
                id=pid[1],
                name=html.unescape(name[1]),
                price=price[1],
                url=f"{self._SITE_URL}{html.unescape(href[1])}",
            )
