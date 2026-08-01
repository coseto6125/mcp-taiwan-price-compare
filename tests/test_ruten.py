"""
Integration tests for the Ruten platform.

These tests make real API calls to verify the adapter works.
Run with: pytest tests/test_ruten.py -v
"""

import pytest

from price_compare.platforms.ruten import RutenPlatform


class TestRuten:
    """Test Ruten platform."""

    @pytest.mark.asyncio
    async def test_search_basic(self) -> None:
        """Test basic search returns results."""
        platform = RutenPlatform()
        products = await platform.search("手錶", max_results=20)
        assert len(products) > 0
        assert all(p.platform == "ruten" for p in products)
        assert all(p.price > 0 for p in products)
        assert all(p.url.startswith("https://") for p in products)

    @pytest.mark.asyncio
    async def test_search_with_min_price(self) -> None:
        """Test min_price filter works."""
        platform = RutenPlatform()
        min_price = 500
        products = await platform.search("手錶", max_results=20, min_price=min_price)
        assert len(products) > 0
        assert all(p.price >= min_price for p in products)

    @pytest.mark.asyncio
    async def test_search_with_max_price(self) -> None:
        """Test max_price filter works."""
        platform = RutenPlatform()
        max_price = 500
        products = await platform.search("手錶", max_results=20, max_price=max_price)
        assert len(products) > 0
        assert all(p.price <= max_price for p in products)

    @pytest.mark.asyncio
    async def test_search_with_require_words(self) -> None:
        """Test require_words filters product names."""
        platform = RutenPlatform()
        products = await platform.search("手錶", max_results=40, require_words=[["機械"]])
        assert len(products) > 0
        assert all("機械" in p.name.lower() for p in products)

    @pytest.mark.asyncio
    async def test_search_include_auction_false_only_buy_now(self) -> None:
        """Test default include_auction=False returns buy-now listings only."""
        platform = RutenPlatform()
        products = await platform.search("耳機", max_results=30, include_auction=False)
        assert len(products) > 0
        assert all(p.platform == "ruten" for p in products)
        assert all(p.price > 0 for p in products)

    @pytest.mark.asyncio
    async def test_search_include_auction_true(self) -> None:
        """Test include_auction=True still returns valid listings."""
        platform = RutenPlatform()
        products = await platform.search("耳機", max_results=30, include_auction=True)
        assert len(products) > 0
        assert all(p.platform == "ruten" for p in products)
        assert all(p.price > 0 for p in products)

    @pytest.mark.asyncio
    async def test_search_no_duplicate_ids(self) -> None:
        """Test results contain no duplicate product URLs."""
        platform = RutenPlatform()
        products = await platform.search("手錶", max_results=50)
        urls = [p.url for p in products]
        assert len(urls) > 0
        assert len(urls) == len(set(urls))
