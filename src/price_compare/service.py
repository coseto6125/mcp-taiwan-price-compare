"""Price comparison service - MCP-ready interface."""

import asyncio
import heapq
from operator import attrgetter
from typing import TYPE_CHECKING, Literal

from price_compare.models import Product, SearchResult
from price_compare.platforms import (
    BooksPlatform,
    Buy123Platform,
    CostcoPlatform,
    CoupangPlatform,
    ETMallPlatform,
    MomoPlatform,
    PChomePlatform,
    PconePlatform,
    PxboxPlatform,
    RakutenPlatform,
    RutenPlatform,
    UniProsperityPlatform,
    YahooAuctionPlatform,
    YahooShoppingPlatform,
)
from price_compare.utils import KeywordGroups, flatten

# Which platforms a multi-platform fan-out covers. Mirrored as a Literal in mcp_server.
type SearchMode = Literal["full", "fast"]
MODES: frozenset[str] = frozenset({"full", "fast"})

if TYPE_CHECKING:
    from price_compare.platforms.base import BasePlatform


class PriceCompareService:
    """Main service for comparing prices across platforms."""

    __slots__ = ("platforms",)

    # A concurrent search costs as much wall-clock as its slowest member, so a site
    # that stalls or refuses connections would otherwise set the latency for all of
    # them. Healthy platforms answer well inside this; a stalled one is simply dropped.
    PLATFORM_TIMEOUT = 3.0

    # Platforms that answer a 100-result query inside 0.5s reliably, measured over
    # randomised interleaved runs across 10 queries: median <= 0.5s and worst case
    # <= 1.2s. The rest are excluded by their own server render time, not by anything
    # client-side (pcone ~1.9s, coupang ~0.9s, momo ~0.9s, rakuten median 0.59s,
    # ruten median 0.57s with an 8s tail). Every platform stays reachable through the
    # single-platform path regardless of which set a fan-out uses.
    FAST_PLATFORMS = frozenset(
        {"etmall", "pchome", "buy123", "yahoo_auction", "yahoo_shopping", "uniprosperity", "pxbox", "books", "costco"}
    )

    def __init__(self) -> None:
        self.platforms: dict[str, BasePlatform] = {
            "books": BooksPlatform(),
            "buy123": Buy123Platform(),
            "costco": CostcoPlatform(),
            "coupang": CoupangPlatform(),
            "etmall": ETMallPlatform(),
            "momo": MomoPlatform(),
            "pchome": PChomePlatform(),
            "pcone": PconePlatform(),
            "pxbox": PxboxPlatform(),
            "rakuten": RakutenPlatform(),
            "ruten": RutenPlatform(),
            "uniprosperity": UniProsperityPlatform(),
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
        mode: SearchMode = "full",
    ) -> SearchResult:
        """
        Search across platforms concurrently.

        Args:
            mode: "full" queries every platform; "fast" queries only FAST_PLATFORMS,
                trading the slower sites' coverage for a sub-second answer.
        """
        args = (query, max_per_platform, min_price, max_price, require_words)
        platforms = self._select(mode)
        results = await asyncio.gather(
            *(asyncio.wait_for(p.search(*args, include_auction=include_auction), self.PLATFORM_TIMEOUT) for p in platforms),
            return_exceptions=True,
        )
        products = list(flatten(r for r in results if isinstance(r, list)))
        return SearchResult(query=query, products=products, total_count=len(products))

    def _select(self, mode: SearchMode) -> list["BasePlatform"]:
        """
        Return the platforms a fan-out in this mode should query.

        Raises:
            ValueError: The mode is not one of MODES. A typo would otherwise fall through
                to the full set and quietly cost seconds per call.
        """
        if mode not in MODES:
            msg = f"unknown mode {mode!r}, expected one of {sorted(MODES)}"
            raise ValueError(msg)
        if mode == "fast":
            return [p for name, p in self.platforms.items() if name in self.FAST_PLATFORMS]
        return list(self.platforms.values())

    async def aclose(self) -> None:
        """Release any connection a platform is holding open across searches."""
        for platform in self.platforms.values():
            closer = getattr(platform, "aclose", None)
            if closer is not None:
                await closer()

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
        mode: SearchMode = "full",
    ) -> list[Product]:
        """Get top N products sorted by price. Uses heapq for O(n log k)."""
        result = await self.search_all_platforms(
            query, max_per_platform, min_price, max_price, require_words, include_auction, mode
        )
        if descending:
            return heapq.nlargest(top_n, result.products, key=attrgetter("price"))
        return heapq.nsmallest(top_n, result.products, key=attrgetter("price"))
