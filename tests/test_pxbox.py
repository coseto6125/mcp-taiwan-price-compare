"""
Integration tests for the PXBox platform.

These tests make real API calls to verify the platform is working.
Run with: pytest tests/test_pxbox.py -v
"""

import pytest

from price_compare.platforms.pxbox import PxboxPlatform, _PxboxProduct


class TestPxbox:
    """Test PXBox platform."""

    @pytest.mark.asyncio
    async def test_search_basic(self) -> None:
        """
        Test basic search returns results.

        Queries here stay in grocery territory: the shared iPhone/手機殼 fixtures only
        ever match a stray accessory listing or two in a supermarket catalogue.
        """
        platform = PxboxPlatform()
        products = await platform.search("餅乾", max_results=5)
        assert len(products) > 0
        assert all(p.platform == "pxbox" for p in products)
        assert all(p.price > 0 for p in products)
        assert all(p.url.startswith("https://") for p in products)

    @pytest.mark.asyncio
    async def test_search_with_min_price(self) -> None:
        """
        Test min_price filter works.

        Results are price-ascending and single-page, so the threshold has to sit
        inside the cheap end the page actually covers - 牛奶 spans roughly $19 to $68.
        """
        platform = PxboxPlatform()
        min_price = 30
        products = await platform.search("牛奶", max_results=20, min_price=min_price)
        assert len(products) > 0
        assert all(p.price >= min_price for p in products)

    @pytest.mark.asyncio
    async def test_search_with_max_price(self) -> None:
        """
        Test max_price filter works.

        The shared 手機殼 fixture matches barely anything in a grocery catalogue, so
        this uses a staple category deep enough to survive individual items selling out.
        """
        platform = PxboxPlatform()
        max_price = 100
        products = await platform.search("餅乾", max_results=10, max_price=max_price)
        assert len(products) > 0
        assert all(p.price <= max_price for p in products)

    @pytest.mark.asyncio
    async def test_search_with_keywords(self) -> None:
        """Test require_words filter works with keyword groups."""
        platform = PxboxPlatform()
        products = await platform.search("咖啡", max_results=10, require_words=[["咖啡"]])
        assert len(products) > 0
        for p in products:
            assert "咖啡" in p.name

    @pytest.mark.asyncio
    async def test_search_keeps_the_cheapest_when_truncating(self) -> None:
        """
        Test a small max_results returns the cheapest of the candidate pool.

        The adapter fetches a fixed 100-item pool and relies on the API's price-ascending
        sort, so truncation must not hand back an arbitrary slice.
        """
        platform = PxboxPlatform()
        pool = await platform.search("餅乾", max_results=50)
        assert len(pool) > 5

        cheapest = sorted(p.price for p in pool)[:5]
        assert sorted(p.price for p in await platform.search("餅乾", max_results=5)) == cheapest


def test_parse_products_drops_sold_out_and_ad_entries() -> None:
    """
    Test sold-out listings and ad placements never reach the caller.

    Neither flag survives onto Product, so this drives the parser directly rather than
    asserting on a live result set that cannot show what was filtered.
    """
    items = [
        _PxboxProduct(id=1, product_name="在架商品", sale_price=50),
        _PxboxProduct(id=2, product_name="售罄商品", sale_price=10, is_sold_out=True),
        _PxboxProduct(id=3, product_name="廣告商品", sale_price=20, is_ad=True),
        _PxboxProduct(id=4, product_name="零元商品", sale_price=0),
        _PxboxProduct(id=5, product_name="重複 id", sale_price=60),
        _PxboxProduct(id=5, product_name="重複 id 第二筆", sale_price=70),
    ]
    platform = PxboxPlatform()
    products = platform.build(platform._extract(items))

    assert [p.name for p in products] == ["在架商品", "重複 id"]
