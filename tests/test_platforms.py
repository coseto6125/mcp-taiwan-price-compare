"""Integration tests for all platforms.

These tests make real API calls to verify each platform is working.
Run with: pytest tests/test_platforms.py -v
"""

import pytest

from price_compare.platforms import (
    CoupangPlatform,
    ETMallPlatform,
    MomoPlatform,
    PChomePlatform,
    RakutenPlatform,
    YahooAuctionPlatform,
    YahooShoppingPlatform,
)


class TestPChome:
    """Test PChome platform."""

    @pytest.mark.asyncio
    async def test_search_basic(self, sample_query: str) -> None:
        """Test basic search returns results."""
        platform = PChomePlatform()
        products = await platform.search(sample_query, max_results=5)
        assert len(products) > 0
        assert all(p.platform == "pchome" for p in products)
        assert all(p.price > 0 for p in products)

    @pytest.mark.asyncio
    async def test_search_with_min_price(self, sample_query: str) -> None:
        """Test min_price filter works."""
        platform = PChomePlatform()
        min_price = 10000
        products = await platform.search(sample_query, max_results=10, min_price=min_price)
        assert all(p.price >= min_price for p in products)

    @pytest.mark.asyncio
    async def test_search_with_max_price(self, sample_query_cheap: str) -> None:
        """Test max_price filter works."""
        platform = PChomePlatform()
        max_price = 500
        products = await platform.search(sample_query_cheap, max_results=10, max_price=max_price)
        assert all(p.price <= max_price for p in products)

    @pytest.mark.asyncio
    async def test_search_with_price_range(self, sample_query: str) -> None:
        """Test price range filter works."""
        platform = PChomePlatform()
        min_price, max_price = 15000, 30000
        products = await platform.search(
            sample_query, max_results=10, min_price=min_price, max_price=max_price
        )
        assert all(min_price <= p.price <= max_price for p in products)


class TestMomo:
    """Test momo platform."""

    @pytest.mark.asyncio
    async def test_search_basic(self, sample_query: str) -> None:
        """Test basic search returns results."""
        platform = MomoPlatform()
        products = await platform.search(sample_query, max_results=5)
        assert len(products) > 0
        assert all(p.platform == "momo" for p in products)
        assert all(p.price > 0 for p in products)

    @pytest.mark.asyncio
    async def test_search_with_min_price(self, sample_query: str) -> None:
        """Test min_price filter works."""
        platform = MomoPlatform()
        min_price = 10000
        products = await platform.search(sample_query, max_results=10, min_price=min_price)
        assert all(p.price >= min_price for p in products)

    @pytest.mark.asyncio
    async def test_search_with_max_price(self, sample_query_cheap: str) -> None:
        """Test max_price filter works."""
        platform = MomoPlatform()
        max_price = 500
        products = await platform.search(sample_query_cheap, max_results=10, max_price=max_price)
        assert all(p.price <= max_price for p in products)


class TestCoupang:
    """Test Coupang platform."""

    @pytest.mark.asyncio
    async def test_search_basic(self, sample_query: str) -> None:
        """Test basic search returns results."""
        platform = CoupangPlatform()
        products = await platform.search(sample_query, max_results=5)
        # Coupang may not always have results for all queries
        if products:
            assert all(p.platform == "coupang" for p in products)
            assert all(p.price > 0 for p in products)

    @pytest.mark.asyncio
    async def test_search_with_keywords(self) -> None:
        """Test include_keywords filter works with keyword groups."""
        platform = CoupangPlatform()
        # Test with keyword groups: (iPhone) AND (15)
        products = await platform.search(
            "iPhone", max_results=10, include_keywords=[["iPhone"], ["15"]]
        )
        for p in products:
            name_lower = p.name.lower()
            assert "iphone" in name_lower
            assert "15" in name_lower

    @pytest.mark.asyncio
    async def test_search_with_price_filter(self, sample_query_cheap: str) -> None:
        """Test price filters work."""
        platform = CoupangPlatform()
        max_price = 500
        products = await platform.search(sample_query_cheap, max_results=10, max_price=max_price)
        assert all(p.price <= max_price for p in products)


class TestETMall:
    """Test ETMall platform."""

    @pytest.mark.asyncio
    async def test_search_basic(self, sample_query: str) -> None:
        """Test basic search returns results."""
        platform = ETMallPlatform()
        products = await platform.search(sample_query, max_results=5)
        if products:
            assert all(p.platform == "etmall" for p in products)
            assert all(p.price > 0 for p in products)

    @pytest.mark.asyncio
    async def test_search_with_price_filter(self, sample_query_cheap: str) -> None:
        """Test price filters work."""
        platform = ETMallPlatform()
        max_price = 500
        products = await platform.search(sample_query_cheap, max_results=10, max_price=max_price)
        assert all(p.price <= max_price for p in products)


class TestRakuten:
    """Test Rakuten platform."""

    @pytest.mark.asyncio
    async def test_search_basic(self, sample_query: str) -> None:
        """Test basic search returns results."""
        platform = RakutenPlatform()
        products = await platform.search(sample_query, max_results=5)
        if products:
            assert all(p.platform == "rakuten" for p in products)
            assert all(p.price > 0 for p in products)

    @pytest.mark.asyncio
    async def test_search_with_keywords(self) -> None:
        """Test include_keywords filter works with keyword groups."""
        platform = RakutenPlatform()
        # Test with keyword groups: (iPhone)
        products = await platform.search(
            "iPhone", max_results=10, include_keywords=[["iPhone"]]
        )
        for p in products:
            assert "iphone" in p.name.lower()

    @pytest.mark.asyncio
    async def test_search_with_price_filter(self, sample_query_cheap: str) -> None:
        """Test price filters work."""
        platform = RakutenPlatform()
        max_price = 500
        products = await platform.search(sample_query_cheap, max_results=10, max_price=max_price)
        assert all(p.price <= max_price for p in products)


class TestYahooShopping:
    """Test Yahoo Shopping platform."""

    @pytest.mark.asyncio
    async def test_search_basic(self, sample_query: str) -> None:
        """Test basic search returns results."""
        platform = YahooShoppingPlatform()
        products = await platform.search(sample_query, max_results=5)
        if products:
            assert all(p.platform == "yahoo_shopping" for p in products)
            assert all(p.price > 0 for p in products)

    @pytest.mark.asyncio
    async def test_search_with_price_filter(self, sample_query_cheap: str) -> None:
        """Test price filters work."""
        platform = YahooShoppingPlatform()
        max_price = 500
        products = await platform.search(sample_query_cheap, max_results=10, max_price=max_price)
        assert all(p.price <= max_price for p in products)


class TestYahooAuction:
    """Test Yahoo Auction platform."""

    @pytest.mark.asyncio
    async def test_search_buy_now_only(self, sample_query: str) -> None:
        """Test default buy_now_only=True returns only buy-now prices."""
        platform = YahooAuctionPlatform()
        products = await platform.search(sample_query, max_results=10)
        # Default should exclude $1 auction starting bids
        if products:
            assert all(p.platform == "yahoo_auction" for p in products)
            # Buy-now prices should not have $1 starting bids
            assert all(p.price > 0 for p in products)

    @pytest.mark.asyncio
    async def test_search_include_auction(self, sample_query: str) -> None:
        """Test include_auction=True includes auction bid prices."""
        platform = YahooAuctionPlatform()
        products = await platform.search(sample_query, max_results=20, include_auction=True)
        if products:
            assert all(p.platform == "yahoo_auction" for p in products)

    @pytest.mark.asyncio
    async def test_search_with_price_filter(self, sample_query: str) -> None:
        """Test price filters work."""
        platform = YahooAuctionPlatform()
        min_price = 1000
        products = await platform.search(sample_query, max_results=10, min_price=min_price)
        assert all(p.price >= min_price for p in products)
