"""Price comparison service - MCP-ready interface."""

import asyncio
import heapq
from operator import attrgetter

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


class PriceCompareService:
    """
    Main service for comparing prices across platforms.

    Designed with MCP integration in mind - each public method can be
    exposed as an MCP tool.
    """

    __slots__ = (
        "_coupang",
        "_etmall",
        "_momo",
        "_pchome",
        "_rakuten",
        "_yahoo_auction",
        "_yahoo_shopping",
    )

    def __init__(self) -> None:
        self._coupang = CoupangPlatform()
        self._etmall = ETMallPlatform()
        self._momo = MomoPlatform()
        self._pchome = PChomePlatform()
        self._rakuten = RakutenPlatform()
        self._yahoo_auction = YahooAuctionPlatform()
        self._yahoo_shopping = YahooShoppingPlatform()

    async def search_all_platforms(
        self,
        query: str,
        max_per_platform: int = 30,
        coupang_keywords: list[str] | None = None,
    ) -> SearchResult:
        """
        Search across all platforms concurrently.

        Args:
            query: Product search keyword
            max_per_platform: Max results per platform
            coupang_keywords: Required keywords for Coupang results (all must match)

        Returns:
            SearchResult with all products
        """
        coupang_task = self._coupang.search(query, max_per_platform, coupang_keywords)
        etmall_task = self._etmall.search(query, max_per_platform)
        momo_task = self._momo.search(query, max_per_platform)
        pchome_task = self._pchome.search(query, max_per_platform)
        rakuten_task = self._rakuten.search(query, max_per_platform)
        yahoo_auction_task = self._yahoo_auction.search(query, max_per_platform)
        yahoo_shopping_task = self._yahoo_shopping.search(query, max_per_platform)

        results = await asyncio.gather(
            coupang_task,
            etmall_task,
            momo_task,
            pchome_task,
            rakuten_task,
            yahoo_auction_task,
            yahoo_shopping_task,
            return_exceptions=True,
        )

        all_products: list[Product] = []
        for result in results:
            if isinstance(result, list):
                all_products.extend(result)

        return SearchResult(
            query=query,
            products=all_products,
            total_count=len(all_products),
        )

    async def get_cheapest(
        self,
        query: str,
        top_n: int = 10,
        max_per_platform: int = 30,
        min_price: int = 0,
        max_price: int = 0,
        descending: bool = False,
        coupang_keywords: list[str] | None = None,
    ) -> list[Product]:
        """
        Get top N products sorted by price.

        Uses heapq for O(n log k) performance.

        Args:
            query: Product search keyword
            top_n: Number of products to return
            max_per_platform: Max results per platform
            min_price: Minimum price filter (0 = no filter)
            max_price: Maximum price filter (0 = no filter)
            descending: True for high-to-low, False for low-to-high
            coupang_keywords: Required keywords for Coupang results (all must match)

        Returns:
            List of top N products with name, price, url, platform
        """
        result = await self.search_all_platforms(query, max_per_platform, coupang_keywords)

        # Apply price filters
        products = result.products
        if min_price > 0:
            products = [p for p in products if p.price >= min_price]
        if max_price > 0:
            products = [p for p in products if p.price <= max_price]

        if descending:
            return heapq.nlargest(top_n, products, key=attrgetter("price"))
        return heapq.nsmallest(top_n, products, key=attrgetter("price"))

    async def search_pchome(self, query: str, max_results: int = 30) -> list[Product]:
        """
        Search only PChome platform.

        MCP Tool: search_pchome
        """
        return await self._pchome.search(query, max_results)

    async def search_momo(self, query: str, max_results: int = 30) -> list[Product]:
        """
        Search only momo platform.

        MCP Tool: search_momo
        """
        return await self._momo.search(query, max_results)

    async def search_coupang(
        self,
        query: str,
        max_results: int = 30,
        required_keywords: list[str] | None = None,
    ) -> list[Product]:
        """
        Search only Coupang Taiwan platform.

        MCP Tool: search_coupang
        """
        return await self._coupang.search(query, max_results, required_keywords)

    async def search_etmall(self, query: str, max_results: int = 30) -> list[Product]:
        """
        Search only ETMall (東森購物) platform.

        MCP Tool: search_etmall
        """
        return await self._etmall.search(query, max_results)

    async def search_rakuten(
        self,
        query: str,
        max_results: int = 30,
        required_keywords: list[str] | None = None,
    ) -> list[Product]:
        """
        Search only Rakuten Taiwan (樂天市場) platform.

        MCP Tool: search_rakuten
        """
        return await self._rakuten.search(query, max_results, required_keywords)

    async def search_yahoo_shopping(
        self, query: str, max_results: int = 30
    ) -> list[Product]:
        """
        Search only Yahoo Shopping (Yahoo購物中心) platform.

        MCP Tool: search_yahoo_shopping
        """
        return await self._yahoo_shopping.search(query, max_results)

    async def search_yahoo_auction(
        self, query: str, max_results: int = 30
    ) -> list[Product]:
        """
        Search only Yahoo Auction (Yahoo拍賣) platform.

        MCP Tool: search_yahoo_auction
        """
        return await self._yahoo_auction.search(query, max_results)


async def compare_prices(query: str, top_n: int = 10) -> list[dict]:
    """
    Compare prices quickly for a given query

    Args:
        query: Product search keyword
        top_n: Number of cheapest products

    Returns:
        List of dicts with name, price, url, platform
    """
    service = PriceCompareService()
    products = await service.get_cheapest(query, top_n)
    return [p.to_dict() for p in products]
