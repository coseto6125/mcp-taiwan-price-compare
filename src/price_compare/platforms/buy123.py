"""生活市集 (buy123.com.tw) platform implementation."""

import re
from collections.abc import Iterator
from contextlib import suppress
from typing import TYPE_CHECKING

import msgspec
import never_primp as primp

if TYPE_CHECKING:
    from never_primp import IMPERSONATE

from price_compare.platforms.base import BasePlatform, Candidate

_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)


class Buy123Platform(BasePlatform[list[dict]]):
    """生活市集 (buy123.com.tw) platform."""

    __slots__ = ("_impersonate", "_timeout")

    name = "buy123"
    # The search page is a server-rendered Next.js page with no public JSON API and no
    # working price-sort parameter, so the pipeline orders what the page carries.
    _SEARCH_URL = "https://www.buy123.com.tw/search"
    _PRODUCT_URL = "https://www.buy123.com.tw/site/sku/{}"

    def __init__(self, impersonate: "IMPERSONATE | None" = "chrome_142", timeout: float = 30.0) -> None:
        self._impersonate = impersonate
        self._timeout = timeout

    async def _fetch(self, query: str, max_results: int, *, include_auction: bool = False) -> list[dict] | None:
        """Request the search page and return the commodities in its __NEXT_DATA__."""
        async with primp.AsyncClient(
            impersonate=self._impersonate,
            impersonate_os="windows",
            timeout=self._timeout,
            http2_only=True,
            headers={"accept": "text/html", "referer": "https://www.buy123.com.tw/"},
        ) as client:
            with suppress(Exception):
                resp = await client.get(self._SEARCH_URL, params={"q": query})
                if resp.status_code != 200 or not (match := _NEXT_DATA_RE.search(resp.text)):
                    return None

                data = msgspec.json.decode(match[1])
                return data["props"]["pageProps"]["searchCommodities"]["commodities"]
        return None

    def _extract(self, payload: list[dict]) -> Iterator[Candidate]:
        """Read commodities out of the page payload."""
        for item in payload:
            item_id, name = item.get("id"), item.get("name")
            display_id = item.get("display_id")
            if not (item_id and name and display_id):
                continue
            yield Candidate(
                id=str(item_id),
                name=name,
                price=item.get("price"),
                url=self._PRODUCT_URL.format(display_id),
            )
