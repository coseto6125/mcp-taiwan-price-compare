"""Ruten (露天市集) platform implementation."""

from contextlib import suppress
from typing import TYPE_CHECKING
from urllib.parse import quote

import msgspec
import never_primp as primp

if TYPE_CHECKING:
    from never_primp import IMPERSONATE

from price_compare.models import Product
from price_compare.platforms.base import BasePlatform
from price_compare.utils import KeywordGroups, matches_keywords, prepare_keyword_groups


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


class RutenPlatform(BasePlatform):
    """Ruten (露天市集) platform."""

    __slots__ = ("_impersonate", "_timeout")

    name = "ruten"
    _SEARCH_URL = "https://rtapi.ruten.com.tw/api/search/v3/index.php/core/prod"
    _ITEMS_URL = "https://rapi.ruten.com.tw/api/items/v2/list"
    _ITEM_URL = "https://www.ruten.com.tw/item/show"

    def __init__(
        self,
        impersonate: "IMPERSONATE | None" = "chrome_142",
        timeout: float = 30.0,
    ) -> None:
        self._impersonate = impersonate
        self._timeout = timeout

    # mypy flags this as an incompatible override: the base absorbs include_auction
    # through **kwargs, and naming it here widens the signature rather than narrowing
    # it, which is safe at runtime but not what mypy's Liskov check accepts.
    async def search(  # type: ignore[override]
        self,
        query: str,
        max_results: int = 100,
        min_price: int = 0,
        max_price: int = 0,
        require_words: KeywordGroups = None,
        include_auction: bool = False,
        **_: object,
    ) -> list[Product]:
        """Search products on Ruten."""
        prepared_keywords = prepare_keyword_groups(require_words)
        # Fixed candidate pool rather than max_results: results arrive by relevance, so a
        # small request would be sorted and truncated from an already-narrow slice and miss
        # the cheaper matches further down. Both round trips are ~0.04s regardless of size.
        params = {"q": query, "limit": "100"}
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
                    return []

                ids = [row.Id for row in _search_decoder.decode(resp.content).Rows if row.Id]
                if not ids:
                    return []

                items_resp = await client.get(self._ITEMS_URL, params={"gno": ",".join(ids)})
                if items_resp.status_code != 200:
                    return []

                items = _items_decoder.decode(items_resp.content).data
                return self._parse_items(items, max_results, min_price, max_price, include_auction, prepared_keywords)
        return []

    def _parse_items(
        self,
        items: list[_Item],
        max_results: int,
        min_price: int,
        max_price: int,
        include_auction: bool,
        prepared_keywords: tuple[tuple[str, ...], ...] | None,
    ) -> list[Product]:
        """Parse item details into a Product list."""
        products: list[Product] = []
        seen_ids: set[str] = set()

        for item in items:
            if not item.name or not item.id:
                continue
            if not include_auction and item.mode != "B":
                continue
            if item.id in seen_ids:
                continue

            price = item.goods_price
            if price <= 0 or (min_price and price < min_price) or (max_price and price > max_price):
                continue
            if not matches_keywords(item.name.lower(), prepared_keywords):
                continue

            seen_ids.add(item.id)
            products.append(Product(name=item.name, price=int(price), url=f"{self._ITEM_URL}?{quote(item.id)}", platform=self.name))

        # The search runs on relevance, not price: Ruten's own price-ascending pages are
        # almost entirely $1 filler listings, so the relevance pool is the better candidate
        # set. Ordering it here means truncation keeps its cheapest members rather than an
        # arbitrary relevance slice.
        products.sort(key=lambda p: p.price)
        return products[:max_results]
