"""博客來 (books.com.tw) platform implementation."""

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

# Search results are server-rendered; each result lives in one grid cell, distinct
# from the "floated-btn-wrap" recommendation footer that reuses the same item ids.
_PRODUCT_DELIMITER = '<div class="table-td" id="prod-itemlist-'
_ID_PATTERN = re.compile(r'^([^"]+)"')
_NAME_PATTERN = re.compile(r'title="([^"]+)"')
# 優惠價 may carry a discount-percent <b> before the actual price; the percent tag
# is never immediately followed by "元", so the non-greedy match skips past it.
_PRICE_PATTERN = re.compile(r"優惠價:.*?<b>([\d,]+)</b>\s*元")


class BooksPlatform(BasePlatform[str]):
    """博客來 (books.com.tw) online bookstore."""

    __slots__ = ("_impersonate", "_timeout")

    name = "books"
    # sort/8 sorts by price ascending (verified empirically against relevance order).
    _SEARCH_URL = "https://search.books.com.tw/search/query/cat/all/sort/8/key/{}"
    _PRODUCT_URL = "https://www.books.com.tw/products/{}"

    def __init__(self, impersonate: "IMPERSONATE | None" = "chrome_142", timeout: float = 30.0) -> None:
        self._impersonate = impersonate
        self._timeout = timeout

    async def _fetch(self, query: str, max_results: int, *, include_auction: bool = False) -> str | None:
        """
        Request the search page and return its HTML.

        博客來 resets connections outright when it throttles a client, so the transport
        error has to be absorbed the same way a non-200 would be.
        """
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
        """Read result cells out of the search HTML."""
        for block in payload.split(_PRODUCT_DELIMITER)[1:]:
            product_id = _ID_PATTERN.search(block)
            name = _NAME_PATTERN.search(block)
            price = _PRICE_PATTERN.search(block)
            if not (product_id and name and price):
                continue

            # Unescape the captured value, never the page: a title holding &quot; would
            # otherwise become a bare quote and close the attribute match early.
            yield Candidate(
                id=product_id[1],
                name=html.unescape(name[1]),
                price=price[1],
                url=self._PRODUCT_URL.format(product_id[1]),
            )
