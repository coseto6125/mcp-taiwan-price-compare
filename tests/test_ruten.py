"""
Integration tests for the Ruten platform.

These tests make real API calls to verify the adapter works.
Run with: pytest tests/test_ruten.py -v
"""

from unittest import mock

import msgspec
import never_primp as primp
import pytest

from price_compare.platforms.ruten import RutenPlatform, _Item

# Every test in this module reaches its platform over the network, so a site outage
# reds it for reasons unrelated to the code. Deselect with `pytest -m "not live"`.
pytestmark = pytest.mark.live


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
    async def test_include_auction_drives_both_the_request_and_the_mode_filter(self) -> None:
        """
        Test the flag reaches the request params and the post-decode mode filter.

        Asserting only that products come back passes even when the flag is ignored
        outright, so this records what _fetch actually asked the site for and what it
        kept from the response.
        """
        platform = RutenPlatform()
        listings = [
            _Item(id="buy-now", name="直購商品", goods_price=500, mode="B"),
            _Item(id="auction", name="競標商品", goods_price=100, mode="A"),
        ]
        asked: list[dict] = []

        class _Client:
            async def get(self, url: str, params: dict | None = None, **_: object):
                asked.append(params or {})
                body = (
                    msgspec.json.encode({"Rows": [{"Id": "buy-now"}, {"Id": "auction"}]})
                    if url == platform._SEARCH_URL
                    else msgspec.json.encode({"data": [msgspec.to_builtins(i) for i in listings]})
                )
                return _Response(body)

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_: object) -> bool:
                return False

        with mock.patch.object(primp, "AsyncClient", return_value=_Client()):
            buy_now = await platform._fetch("手錶", 100, include_auction=False)
            asked.clear()
            everything = await platform._fetch("手錶", 100, include_auction=True)

        assert [i.id for i in buy_now] == ["buy-now"], "auction listings must be filtered out"
        assert [i.id for i in everything] == ["buy-now", "auction"], "the flag must let auctions through"
        assert "type" not in asked[0], "include_auction=True must not send type=direct"

    @pytest.mark.asyncio
    async def test_search_include_auction_true_against_the_live_site(self) -> None:
        """Test the flag path still works end to end."""
        platform = RutenPlatform()
        products = await platform.search("手錶", max_results=20, include_auction=True)
        assert len(products) > 0
        assert all(p.platform == "ruten" for p in products)

    @pytest.mark.asyncio
    async def test_search_no_duplicate_ids(self) -> None:
        """Test results contain no duplicate product URLs."""
        platform = RutenPlatform()
        products = await platform.search("手錶", max_results=50)
        urls = [p.url for p in products]
        assert len(urls) > 0
        assert len(urls) == len(set(urls))

    @pytest.mark.asyncio
    async def test_search_returns_price_ascending(self) -> None:
        """
        Test results arrive cheapest-first.

        Ruten is searched on relevance because its own price-ascending pages are almost
        entirely $1 filler, so the adapter orders the relevance pool itself.
        """
        platform = RutenPlatform()
        products = await platform.search("咖啡", max_results=50)
        assert len(products) > 1
        assert [p.price for p in products] == sorted(p.price for p in products)

    @pytest.mark.asyncio
    async def test_search_keeps_the_cheapest_when_truncating(self) -> None:
        """
        Test a small max_results returns the pool's cheapest, not its first N.

        Regression guard: max_results used to size the API request and break the parse
        loop early, so search("咖啡", 5) returned relevance-ordered items while cheaper
        ones sat further down the same pool.
        """
        platform = RutenPlatform()
        pool = await platform.search("咖啡", max_results=100)
        assert len(pool) > 5

        cheapest = sorted(p.price for p in pool)[:5]
        assert sorted(p.price for p in await platform.search("咖啡", max_results=5)) == cheapest


class _Response:
    """Minimal stand-in for a primp response."""

    def __init__(self, content: bytes) -> None:
        self.content, self.status_code = content, 200
