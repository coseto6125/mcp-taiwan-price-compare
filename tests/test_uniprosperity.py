"""
Integration tests for the Uni-Prosperity platform.

These tests make real API calls to verify the platform is working.
Run with: pytest tests/test_uniprosperity.py -v
"""

import pytest

from price_compare.platforms.uniprosperity import UniProsperityPlatform


class TestUniProsperity:
    """Test Uni-Prosperity platform."""

    @pytest.mark.asyncio
    async def test_search_basic(self) -> None:
        """Test basic search returns results with correct platform, prices, and URLs."""
        platform = UniProsperityPlatform()
        products = await platform.search("衛生紙", max_results=10)
        assert len(products) > 0
        assert all(p.platform == "uniprosperity" for p in products)
        assert all(p.price > 0 for p in products)
        assert all(p.url.startswith("https://online.uni-prosperity.com.tw/") for p in products)

    @pytest.mark.asyncio
    async def test_search_with_min_price(self) -> None:
        """Test min_price filter works."""
        platform = UniProsperityPlatform()
        min_price = 200
        products = await platform.search("衛生紙", max_results=10, min_price=min_price)
        assert len(products) > 0
        assert all(p.price >= min_price for p in products)

    @pytest.mark.asyncio
    async def test_search_with_max_price(self) -> None:
        """Test max_price filter works."""
        platform = UniProsperityPlatform()
        max_price = 200
        products = await platform.search("衛生紙", max_results=10, max_price=max_price)
        assert len(products) > 0
        assert all(p.price <= max_price for p in products)

    @pytest.mark.asyncio
    async def test_search_with_keywords(self) -> None:
        """Test require_words filter works with keyword groups."""
        platform = UniProsperityPlatform()
        products = await platform.search("咖啡", max_results=10, require_words=[["咖啡"]])
        assert len(products) > 0
        assert all("咖啡" in p.name for p in products)

    @pytest.mark.asyncio
    async def test_search_returns_price_ascending(self) -> None:
        """Test the full result set is sorted cheapest-first before truncation."""
        platform = UniProsperityPlatform()
        products = await platform.search("衛生紙", max_results=20)
        assert len(products) > 1
        assert [p.price for p in products] == sorted(p.price for p in products)

    @pytest.mark.asyncio
    async def test_search_deduplicates_repeated_tiles(self) -> None:
        """Test each product appears once even though the markup repeats its id."""
        platform = UniProsperityPlatform()
        products = await platform.search("衛生紙", max_results=50)
        assert len(products) > 1
        assert len({p.url for p in products}) == len(products)
