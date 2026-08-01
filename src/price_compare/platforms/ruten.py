"""Ruten (露天市集) platform implementation."""

import asyncio
from collections.abc import Iterator
from contextlib import suppress
from typing import TYPE_CHECKING
from urllib.parse import quote

import msgspec
import never_primp as primp

if TYPE_CHECKING:
    from never_primp import IMPERSONATE

from price_compare.platforms.base import BasePlatform, Candidate


class _SearchRow(msgspec.Struct):
    """Single row from the Ruten product search index."""

    Id: str = ""


class _SearchResponse(msgspec.Struct):
    """Ruten product search response."""

    Rows: list[_SearchRow] = []


class _Item(msgspec.Struct):
    """Ruten item detail from the batch item lookup API."""

    id: str = ""
    name: str = ""
    goods_price: float = 0.0
    mode: str = ""


class _ItemsResponse(msgspec.Struct):
    """Ruten batch item lookup response."""

    data: list[_Item] = []


_search_decoder = msgspec.json.Decoder(_SearchResponse, strict=False)
_items_decoder = msgspec.json.Decoder(_ItemsResponse, strict=False)


class RutenPlatform(BasePlatform[list[_Item]]):
    """Ruten (露天市集) platform."""

    __slots__ = ("_impersonate", "_timeout")

    name = "ruten"
    # Searched on relevance: Ruten's own price-ascending pages are almost entirely $1
    # filler listings, so the relevance pool is the better candidate set and the
    # pipeline orders it.
    _SEARCH_URL = "https://rtapi.ruten.com.tw/api/search/v3/index.php/core/prod"
    _ITEMS_URL = "https://rapi.ruten.com.tw/api/items/v2/list"
    _ITEM_URL = "https://www.ruten.com.tw/item/show"
    _POOL_SIZE = "100"
    _ITEM_ATTEMPTS = 3
    _RETRY_DELAY = 0.3

    def __init__(self, impersonate: "IMPERSONATE | None" = "chrome_142", timeout: float = 30.0) -> None:
        self._impersonate = impersonate
        self._timeout = timeout

    async def _fetch(self, query: str, max_results: int, *, include_auction: bool = False) -> list[_Item] | None:
        """
        Resolve the search index to item details, in two round trips.

        The index returns bare ids, so a second batch call fetches names and prices.
        A fixed pool rather than max_results: results arrive by relevance, so a small
        request would be ordered and truncated from an already-narrow slice.
        """
        params = {"q": query, "limit": self._POOL_SIZE}
        if not include_auction:
            params["type"] = "direct"

        async with primp.AsyncClient(
            impersonate=self._impersonate,
            impersonate_os="windows",
            timeout=self._timeout,
            headers={"referer": "https://www.ruten.com.tw/"},
        ) as client:
            with suppress(Exception):
                resp = await client.get(self._SEARCH_URL, params=params)
                if resp.status_code != 200:
                    return None

                ids = [row.Id for row in _search_decoder.decode(resp.content).Rows if row.Id]
                if not ids:
                    return None

                # The batch item endpoint intermittently answers 502/503 and succeeds on
                # a retry moments later, independent of how many ids the batch carries.
                params_items = {"gno": ",".join(ids)}
                for attempt in range(self._ITEM_ATTEMPTS):
                    items_resp = await client.get(self._ITEMS_URL, params=params_items)
                    if items_resp.status_code == 200:
                        items = _items_decoder.decode(items_resp.content).data
                        # mode "B" marks buy-now. type=direct already excludes auctions
                        # request-side; this holds the same line on the decoded payload.
                        return items if include_auction else [i for i in items if i.mode == "B"]
                    if attempt + 1 < self._ITEM_ATTEMPTS:
                        await asyncio.sleep(self._RETRY_DELAY)
        return None

    def _extract(self, payload: list[_Item]) -> Iterator[Candidate]:
        """Read listings out of the item details."""
        for item in payload:
            yield Candidate(
                id=item.id,
                name=item.name,
                price=item.goods_price,
                url=f"{self._ITEM_URL}?{quote(item.id)}",
            )
