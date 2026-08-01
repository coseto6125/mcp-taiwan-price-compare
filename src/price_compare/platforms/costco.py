"""Costco Taiwan (好市多) platform implementation."""

from collections.abc import Iterator
from contextlib import suppress
from typing import TYPE_CHECKING

import msgspec
import never_primp as primp

if TYPE_CHECKING:
    from never_primp import IMPERSONATE

from price_compare.platforms.base import BasePlatform, Candidate


class CostcoPlatform(BasePlatform[list[dict]]):
    """Costco Taiwan (好市多) platform."""

    __slots__ = ("_impersonate", "_timeout")

    name = "costco"
    # Server-side price sort keeps the query intact (same totalResults as relevance) and
    # reaches cheap items that rank past the first page, which sorting one relevance page
    # client-side would miss. It leads with in-warehouse-only items carrying no price at
    # all, which the pipeline drops for having no readable price.
    _SEARCH_URL = "https://www.costco.com.tw/rest/v2/taiwan/products/search"
    _BASE_URL = "https://www.costco.com.tw"

    def __init__(self, impersonate: "IMPERSONATE | None" = "chrome_142", timeout: float = 30.0) -> None:
        self._impersonate = impersonate
        self._timeout = timeout

    async def _fetch(self, query: str, max_results: int, *, include_auction: bool = False) -> list[dict] | None:
        """Request the OCC search endpoint and return its product entries."""
        params = {
            "query": query,
            "fields": "FULL",
            "lang": "zh_TW",
            "curr": "TWD",
            "sort": "price-asc",
            "pageSize": "100",
        }

        async with primp.AsyncClient(
            impersonate=self._impersonate,
            impersonate_os="windows",
            timeout=self._timeout,
            http2_only=True,
            headers={"accept": "application/json", "referer": "https://www.costco.com.tw/search"},
        ) as client:
            with suppress(Exception):
                resp = await client.get(self._SEARCH_URL, params=params)
                if resp.status_code != 200:
                    return None
                return msgspec.json.decode(resp.content).get("products")
        return None

    def _extract(self, payload: list[dict]) -> Iterator[Candidate]:
        """Read products out of the decoded response."""
        for item in payload:
            code, name, url = item.get("code"), item.get("name"), item.get("url")
            price = (item.get("price") or {}).get("value")
            if not (code and name and url):
                continue
            yield Candidate(id=code, name=name, price=price, url=f"{self._BASE_URL}{url}")
