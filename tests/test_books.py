"""
Integration tests for the 博客來 (books.com.tw) platform.

These tests make real API calls to verify the platform is working.
Run with: pytest tests/test_books.py -v
"""

import pytest

from price_compare.platforms.books import BooksPlatform

# Every test in this module reaches its platform over the network, so a site outage
# reds it for reasons unrelated to the code. Deselect with `pytest -m "not live"`.
pytestmark = pytest.mark.live


class TestBooks:
    """Test 博客來 platform."""

    @pytest.mark.asyncio
    async def test_search_basic(self) -> None:
        """Test basic search returns results with correct platform, prices, and URLs."""
        platform = BooksPlatform()
        products = await platform.search("哈利波特", max_results=10)
        assert len(products) > 0
        assert all(p.platform == "books" for p in products)
        assert all(p.price > 0 for p in products)
        assert all(p.url.startswith("https://www.books.com.tw/") for p in products)

    @pytest.mark.asyncio
    async def test_search_with_max_price(self) -> None:
        """
        Test max_price filter works.

        衛生紙 spans roughly $59 to $180 across the full page of 60 results, so a
        $100 cap genuinely excludes the pricier half rather than passing vacuously.
        """
        platform = BooksPlatform()
        max_price = 100
        products = await platform.search("衛生紙", max_results=60, max_price=max_price)
        assert len(products) > 0
        assert all(p.price <= max_price for p in products)

    @pytest.mark.asyncio
    async def test_search_with_min_price(self) -> None:
        """
        Test min_price filter works.

        Results come back price-ascending, so the query must be one whose cheap
        end still clears the threshold within the fetched page - 哈利波特 spans
        roughly $198 to well past $300 within the first 15 ascending results.
        """
        platform = BooksPlatform()
        min_price = 250
        products = await platform.search("哈利波特", max_results=15, min_price=min_price)
        assert len(products) > 0
        assert all(p.price >= min_price for p in products)

    @pytest.mark.asyncio
    async def test_search_with_require_words(self) -> None:
        """
        Test require_words filter works.

        洗髮精 results include unrelated MUJI 護髮 (hair-conditioning, not shampoo)
        products ranked ahead of the 洗髮 (shampoo) ones, so this genuinely excludes
        items rather than passing vacuously.
        """
        platform = BooksPlatform()
        products = await platform.search("洗髮精", max_results=100, require_words=[["洗髮"]])
        assert len(products) > 0
        assert all("洗髮" in p.name for p in products)

    @pytest.mark.asyncio
    async def test_search_has_no_duplicate_urls(self) -> None:
        """Test dedup by product id leaves no repeated entries."""
        platform = BooksPlatform()
        products = await platform.search("哈利波特", max_results=60)
        assert len(products) > 1
        assert len({p.url for p in products}) == len(products)
