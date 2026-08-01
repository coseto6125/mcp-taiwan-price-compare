"""
Integration tests for the 生活市集 (buy123) platform.

These tests make real API calls to verify the platform is working.
Run with: pytest tests/test_buy123.py -v
"""

import pytest

from price_compare.platforms.buy123 import Buy123Platform


class TestBuy123:
    """Test buy123 platform."""

    @pytest.mark.asyncio
    async def test_search_basic(self) -> None:
        """Test basic search returns results with correct platform, prices, and URLs."""
        platform = Buy123Platform()
        products = await platform.search("咖啡", max_results=5)
        assert len(products) > 0
        assert all(p.platform == "buy123" for p in products)
        assert all(p.price > 0 for p in products)
        assert all(p.url.startswith("https://www.buy123.com.tw/site/sku/") for p in products)

    @pytest.mark.asyncio
    async def test_search_with_max_price(self) -> None:
        """Test max_price filter works."""
        platform = Buy123Platform()
        max_price = 500
        products = await platform.search("洗髮精", max_results=20, max_price=max_price)
        assert len(products) > 1
        assert all(p.price <= max_price for p in products)

    @pytest.mark.asyncio
    async def test_search_with_min_price(self) -> None:
        """Test min_price filter works."""
        platform = Buy123Platform()
        min_price = 1000
        products = await platform.search("衛生紙", max_results=20, min_price=min_price)
        assert len(products) > 1
        assert all(p.price >= min_price for p in products)

    @pytest.mark.asyncio
    async def test_search_with_require_words(self) -> None:
        """Test require_words filter works with keyword groups."""
        platform = Buy123Platform()
        products = await platform.search("洗髮精", max_results=20, require_words=[["洗髮", "shampoo"]])
        assert len(products) > 0
        assert all("洗髮" in p.name or "shampoo" in p.name.lower() for p in products)

    @pytest.mark.asyncio
    async def test_search_has_no_duplicate_ids(self) -> None:
        """Test dedup by product id leaves no repeated entries."""
        platform = Buy123Platform()
        products = await platform.search("咖啡", max_results=50)
        assert len(products) > 1
        assert len({p.url for p in products}) == len(products)
