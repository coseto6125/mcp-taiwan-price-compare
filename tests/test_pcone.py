"""
Integration tests for the pcone (松果購物) platform.

These tests make real API calls to verify the platform is working.
Run with: pytest tests/test_pcone.py -v
"""

import pytest

from price_compare.platforms.pcone import PconePlatform


class TestPcone:
    """Test pcone platform."""

    @pytest.mark.asyncio
    async def test_search_basic(self, sample_query: str) -> None:
        """Test basic search returns results."""
        platform = PconePlatform()
        products = await platform.search(sample_query, max_results=5)
        assert len(products) > 0
        assert all(p.platform == "pcone" for p in products)
        assert all(p.price > 0 for p in products)
        assert all(p.url.startswith("https://pcone.com.tw/product/info/") for p in products)

    @pytest.mark.asyncio
    async def test_search_with_min_price(self, sample_query_cheap: str) -> None:
        """Test min_price filter works."""
        platform = PconePlatform()
        min_price = 200
        products = await platform.search(sample_query_cheap, max_results=20, min_price=min_price)
        assert len(products) > 0
        assert all(p.price >= min_price for p in products)

    @pytest.mark.asyncio
    async def test_search_with_max_price(self, sample_query_cheap: str) -> None:
        """Test max_price filter works."""
        platform = PconePlatform()
        max_price = 200
        products = await platform.search(sample_query_cheap, max_results=20, max_price=max_price)
        assert len(products) > 0
        assert all(p.price <= max_price for p in products)

    @pytest.mark.asyncio
    async def test_search_with_keywords(self, sample_query_cheap: str) -> None:
        """Test require_words filter works with keyword groups."""
        platform = PconePlatform()
        products = await platform.search(
            sample_query_cheap, max_results=20, require_words=[["iphone"]]
        )
        assert len(products) > 0
        assert all("iphone" in p.name.lower() for p in products)

    @pytest.mark.asyncio
    async def test_search_no_duplicate_ids(self, sample_query_cheap: str) -> None:
        """Test search results contain no duplicate products."""
        platform = PconePlatform()
        products = await platform.search(sample_query_cheap, max_results=50)
        assert len(products) > 0
        urls = [p.url for p in products]
        assert len(urls) == len(set(urls))

    @pytest.mark.asyncio
    async def test_search_truncates_to_max_results(self) -> None:
        """
        Test max_results bounds the result count.

        The API returns a seed-randomised sample rather than a stable ranking, so two
        calls draw different pools and a cheapest-set comparison across them would be
        flaky. The cheapest-first guarantee is asserted within one call below instead.
        """
        platform = PconePlatform()
        products = await platform.search("咖啡", max_results=5)
        # Both bounds: a search that returned nothing would satisfy the upper one alone.
        assert 0 < len(products) <= 5

    @pytest.mark.asyncio
    async def test_search_returns_price_ascending(self) -> None:
        """Test results arrive cheapest-first."""
        platform = PconePlatform()
        products = await platform.search("咖啡", max_results=30)
        assert len(products) > 1
        assert [p.price for p in products] == sorted(p.price for p in products)
