"""Price comparison service - MCP-ready interface."""

import asyncio
import heapq
from operator import attrgetter
from tkinter import _flatten  # noqa:RUF100  # type: ignore[attr-defined]
from typing import TYPE_CHECKING

from price_compare.models import Product, SearchResult
from price_compare.platforms import (
    CoupangPlatform,
    ETMallPlatform,
    MomoPlatform,
    PChomePlatform,
    RakutenPlatform,
    YahooAuctionPlatform,
    YahooShoppingPlatform,
)
from price_compare.utils import KeywordGroups

if TYPE_CHECKING:
    from price_compare.platforms.base import BasePlatform


class PriceCompareService:
    """Main service for comparing prices across platforms."""

    __slots__ = ("platforms",)

    def __init__(self) -> None:
        self.platforms: dict[str, BasePlatform] = {
            "coupang": CoupangPlatform(),
            "etmall": ETMallPlatform(),
            "momo": MomoPlatform(),
            "pchome": PChomePlatform(),
            "rakuten": RakutenPlatform(),
            "yahoo_auction": YahooAuctionPlatform(),
            "yahoo_shopping": YahooShoppingPlatform(),
        }

    async def search_all_platforms(
        self,
        query: str,
        max_per_platform: int = 100,
        min_price: int = 0,
        max_price: int = 0,
        require_words: KeywordGroups = None,
        include_auction: bool = False,
    ) -> SearchResult:
        """Search across all platforms concurrently."""
        args = (query, max_per_platform, min_price, max_price, require_words)
        results = await asyncio.gather(
            *(p.search(*args, include_auction=include_auction) for p in self.platforms.values()),
            return_exceptions=True,
        )
        products = list(_flatten([r for r in results if isinstance(r, list)]))
        return SearchResult(query=query, products=products, total_count=len(products))

    async def get_cheapest(
        self,
        query: str,
        top_n: int = 10,
        max_per_platform: int = 50,
        min_price: int = 0,
        max_price: int = 0,
        descending: bool = False,
        require_words: KeywordGroups = None,
        include_auction: bool = False,
    ) -> list[Product]:
        """Get top N products sorted by price. Uses heapq for O(n log k)."""
        result = await self.search_all_platforms(query, max_per_platform, min_price, max_price, require_words, include_auction)
        if descending:
            return heapq.nlargest(top_n, result.products, key=attrgetter("price"))
        return heapq.nsmallest(top_n, result.products, key=attrgetter("price"))
