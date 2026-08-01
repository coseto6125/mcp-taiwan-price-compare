"""
Integration tests for the Costco platform.

These tests make real API calls to verify the platform is working.
Run with: pytest tests/test_costco.py -v
"""

import pytest

from price_compare.platforms.costco import CostcoPlatform


class TestCostco:
    """Test Costco platform."""

    @pytest.mark.asyncio
    async def test_search_basic(self) -> None:
        """Test basic search returns results with correct platform, prices, and URLs."""
        platform = CostcoPlatform()
        products = await platform.search("咖啡", max_results=5)
        assert len(products) > 0
        assert all(p.platform == "costco" for p in products)
        assert all(p.price > 0 for p in products)
        assert all(p.url.startswith("https://www.costco.com.tw/") for p in products)

    @pytest.mark.asyncio
    async def test_search_with_max_price(self) -> None:
        """Test max_price filter works."""
        platform = CostcoPlatform()
        max_price = 500
        products = await platform.search("咖啡", max_results=10, max_price=max_price)
        assert len(products) > 0
        assert all(p.price <= max_price for p in products)

    @pytest.mark.asyncio
    async def test_search_with_min_price(self) -> None:
        """
        Test min_price filter works.

        Results come back price-ascending from a single page, so the query must be
        one whose cheap end still clears the threshold - 衛生紙 spans $375 to $15569.
        """
        platform = CostcoPlatform()
        min_price = 1000
        products = await platform.search("衛生紙", max_results=10, min_price=min_price)
        assert len(products) > 0
        assert all(p.price >= min_price for p in products)

    @pytest.mark.asyncio
    async def test_search_with_require_words(self) -> None:
        """Test require_words filter works with keyword groups."""
        platform = CostcoPlatform()
        products = await platform.search("洗髮精", max_results=10, require_words=[["洗髮", "shampoo"]])
        assert len(products) > 0
        assert all("洗髮" in p.name or "shampoo" in p.name.lower() for p in products)

    @pytest.mark.asyncio
    async def test_search_returns_price_ascending(self) -> None:
        """Test results arrive cheapest-first so truncation keeps the cheapest."""
        platform = CostcoPlatform()
        products = await platform.search("咖啡", max_results=20)
        assert len(products) > 1
        assert [p.price for p in products] == sorted(p.price for p in products)

    @pytest.mark.asyncio
    async def test_search_has_no_duplicate_urls(self) -> None:
        """Test dedup by product code leaves no repeated entries."""
        platform = CostcoPlatform()
        products = await platform.search("咖啡", max_results=50)
        assert len(products) > 1
        assert len({p.url for p in products}) == len(products)
