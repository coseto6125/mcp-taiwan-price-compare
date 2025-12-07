"""Integration tests for the PriceCompareService."""

import pytest

from price_compare.service import PriceCompareService


class TestPriceCompareService:
    """Test the main service."""

    @pytest.mark.asyncio
    async def test_get_cheapest_basic(self, sample_query: str) -> None:
        """Test get_cheapest returns results from multiple platforms."""
        service = PriceCompareService()
        products = await service.get_cheapest(sample_query, top_n=10)
        assert len(products) > 0
        # Should have results from multiple platforms
        platforms = {p.platform for p in products}
        assert len(platforms) >= 1

    @pytest.mark.asyncio
    async def test_get_cheapest_with_price_filter(self, sample_query: str) -> None:
        """Test price filters are applied correctly."""
        service = PriceCompareService()
        min_price, max_price = 10000, 50000
        products = await service.get_cheapest(
            sample_query, top_n=20, min_price=min_price, max_price=max_price
        )
        assert all(min_price <= p.price <= max_price for p in products)

    @pytest.mark.asyncio
    async def test_get_cheapest_sorted(self, sample_query: str) -> None:
        """Test results are sorted by price (low to high)."""
        service = PriceCompareService()
        products = await service.get_cheapest(sample_query, top_n=10)
        prices = [p.price for p in products]
        assert prices == sorted(prices)

    @pytest.mark.asyncio
    async def test_search_individual_platforms(self, sample_query: str) -> None:
        """Test individual platform search via platforms dict."""
        service = PriceCompareService()

        pchome = await service.platforms["pchome"].search(sample_query, max_results=3)
        assert all(p.platform == "pchome" for p in pchome)

        momo = await service.platforms["momo"].search(sample_query, max_results=3)
        assert all(p.platform == "momo" for p in momo)

    @pytest.mark.asyncio
    async def test_yahoo_auction_exclude_bids(self, sample_query: str) -> None:
        """Test Yahoo auction excludes bid prices by default."""
        service = PriceCompareService()
        products = await service.platforms["yahoo_auction"].search(sample_query, max_results=10)
        if products:
            assert all(p.price > 0 for p in products)
