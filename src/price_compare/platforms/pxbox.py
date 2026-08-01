"""PXBox (全聯全電商) platform implementation."""

from collections.abc import Iterator
from contextlib import suppress
from typing import TYPE_CHECKING

import msgspec
import never_primp as primp

if TYPE_CHECKING:
    from never_primp import IMPERSONATE

from price_compare.platforms.base import BasePlatform, Candidate


class _PxboxProduct(msgspec.Struct):
    """PXBox product from API response."""

    id: int = 0
    product_name: str = ""
    sale_price: float = 0.0
    is_sold_out: bool = False
    is_ad: bool = False


class _PxboxData(msgspec.Struct):
    """PXBox search response data payload."""

    product_list: list[_PxboxProduct] = []


class _PxboxResponse(msgspec.Struct):
    """PXBox search response structure."""

    code: str = ""
    data: _PxboxData | None = None


_decoder = msgspec.json.Decoder(_PxboxResponse, strict=False)


class PxboxPlatform(BasePlatform[list[_PxboxProduct]]):
    """PXBox (全聯全電商, PX Mart's nationwide-shipping storefront) platform."""

    __slots__ = ("_impersonate", "_timeout")

    name = "pxbox"
    # sort_type 3 (price) + sort_order 1 (ascending), verified empirically: sort_order 0
    # falls back to relevance and 2 is descending.
    _SEARCH_URL = "https://api-pxbox.es.pxmart.com.tw/app/2.0/spu/single_search"
    _SITE_URL = "https://pxbox.es.pxmart.com.tw"
    _SUCCESS_CODE = "0000"

    def __init__(self, impersonate: "IMPERSONATE | None" = "chrome_142", timeout: float = 30.0) -> None:
        self._impersonate = impersonate
        self._timeout = timeout

    async def _fetch(self, query: str, max_results: int, *, include_auction: bool = False) -> list[_PxboxProduct] | None:
        """Request the search API and return its product entries."""
        payload = msgspec.json.encode(
            {
                "search_setting_type": 2,
                "keyword": query,
                "sort_type": 3,
                "sort_order": 1,
                "page_index": 1,
                # Fixed pool rather than max_results: sold-out and ad entries are dropped
                # after the fact, so a small request would come back empty.
                "page_size": 100,
                "filters": [],
            }
        )

        async with primp.AsyncClient(
            impersonate=self._impersonate,
            impersonate_os="windows",
            timeout=self._timeout,
            headers={"content-type": "application/json", "origin": self._SITE_URL, "referer": f"{self._SITE_URL}/"},
        ) as client:
            with suppress(Exception):
                resp = await client.post(self._SEARCH_URL, content=payload)
                if resp.status_code != 200:
                    return None

                decoded = _decoder.decode(resp.content)
                if decoded.code != self._SUCCESS_CODE or decoded.data is None:
                    return None
                return decoded.data.product_list
        return None

    def _extract(self, payload: list[_PxboxProduct]) -> Iterator[Candidate]:
        """Read in-stock, non-ad products out of the decoded response."""
        for item in payload:
            # Sold-out listings and ad placements are not genuine cheapest-price matches.
            if item.is_sold_out or item.is_ad:
                continue
            yield Candidate(
                id=str(item.id),
                name=item.product_name,
                price=item.sale_price,
                url=f"{self._SITE_URL}/product/{item.id}",
            )
