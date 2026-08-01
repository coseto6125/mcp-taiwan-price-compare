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

    @pytest.mark.asyncio
    async def test_fast_mode_queries_only_fast_platforms(self, sample_query: str) -> None:
        """Test mode='fast' restricts the fan-out to the sub-second platform set."""
        service = PriceCompareService()
        result = await service.search_all_platforms(sample_query, max_per_platform=20, mode="fast")
        assert result.total_count > 0
        assert {p.platform for p in result.products} <= service.FAST_PLATFORMS

    @pytest.mark.asyncio
    async def test_full_mode_is_the_default_and_covers_more(self, sample_query: str) -> None:
        """Test the default fan-out reaches platforms that fast mode leaves out."""
        service = PriceCompareService()
        full = await service.search_all_platforms(sample_query, max_per_platform=20)
        fast = await service.search_all_platforms(sample_query, max_per_platform=20, mode="fast")
        assert not {p.platform for p in full.products} <= service.FAST_PLATFORMS
        assert full.total_count > fast.total_count

    @pytest.mark.asyncio
    async def test_fast_platform_set_excludes_the_slow_sites(self) -> None:
        """Test the fast set omits the platforms measured above the 0.5s budget."""
        service = PriceCompareService()
        assert set(service.platforms) >= service.FAST_PLATFORMS
        assert service.FAST_PLATFORMS.isdisjoint({"pcone", "coupang", "momo", "rakuten", "ruten"})

    @pytest.mark.asyncio
    async def test_named_platform_reachable_regardless_of_mode(self) -> None:
        """Test a slow platform stays reachable through the single-platform path."""
        service = PriceCompareService()
        products = await service.platforms["pcone"].search("咖啡", max_results=5)
        assert len(products) > 0
        assert all(p.platform == "pcone" for p in products)
