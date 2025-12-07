"""Yahoo Auction (Yahoo拍賣) platform implementation."""

from contextlib import suppress
from typing import TYPE_CHECKING

import msgspec
import never_primp as primp

if TYPE_CHECKING:
    from never_primp import IMPERSONATE

from price_compare.models import Product
from price_compare.platforms.base import BasePlatform
from price_compare.utils import KeywordGroups, matches_keywords, prepare_keyword_groups

# GraphQL persisted query hash - may need update if Yahoo changes their frontend
_GRAPHQL_HASH = "9e8c95a7bd216439855a6dcb580387b180713a20260a89c26096fbe4dd30133f"

# HTML fallback markers
_ISOREDUX_START = b'<script id="isoredux-data" type="mime/invalid">'
_ISOREDUX_END = b"</script>"


class _YahooAuctionProduct(msgspec.Struct):
    """Yahoo Auction product from API response."""

    ec_title: str = ""
    ec_price: float = 0.0
    ec_buyprice: float = 0.0
    ec_item_url: str = ""
    ec_productid: str = ""


class _GetUther(msgspec.Struct):
    """GraphQL getUther response."""

    hits: list[_YahooAuctionProduct] = []


class _GraphQLData(msgspec.Struct, rename="camel"):
    """GraphQL data wrapper."""

    get_uther: _GetUther | None = None


class _GraphQLResponse(msgspec.Struct):
    """GraphQL response structure."""

    data: _GraphQLData | None = None


# HTML fallback structures
class _EcSearch(msgspec.Struct):
    hits: list[_YahooAuctionProduct] = []


class _Search(msgspec.Struct):
    ecsearch: _EcSearch = msgspec.field(default_factory=_EcSearch)


class _IsoreduxData(msgspec.Struct):
    search: _Search = msgspec.field(default_factory=_Search)


_graphql_decoder = msgspec.json.Decoder(_GraphQLResponse, strict=False)
_html_decoder = msgspec.json.Decoder(_IsoreduxData, strict=False)


class YahooAuctionPlatform(BasePlatform):
    """Yahoo Auction (Yahoo拍賣) platform."""

    __slots__ = ("_impersonate", "_timeout")

    name = "yahoo_auction"
    _GRAPHQL_URL = "https://graphql.ec.yahoo.com/graphql"
    _HTML_URL = "https://tw.bid.yahoo.com/search/auction/product"

    def __init__(
        self,
        impersonate: "IMPERSONATE | None" = "chrome_142",
        timeout: float = 30.0,
    ) -> None:
        self._impersonate = impersonate
        self._timeout = timeout

    async def search(
        self,
        query: str,
        max_results: int = 100,
        min_price: int = 0,
        max_price: int = 0,
        include_keywords: KeywordGroups = None,
        include_auction: bool = False,
        **_: object,
    ) -> list[Product]:
        """Search products on Yahoo Auction."""
        prepared_keywords = prepare_keyword_groups(include_keywords)
        buy_now_only = not include_auction

        # Try GraphQL first, fallback to HTML
        return await self._search_graphql(query, max_results, min_price, max_price, buy_now_only, prepared_keywords) or await self._search_html(query, max_results, min_price, max_price, buy_now_only, prepared_keywords)

    async def _search_graphql(
        self, query: str, max_results: int, min_price: int, max_price: int, buy_now_only: bool, prepared_keywords: tuple[tuple[str, ...], ...] | None
    ) -> list[Product]:
        """Search using GraphQL API."""
        payload = msgspec.json.encode({
            "variables": {"property": "auction", "cid": "0", "clv": "0", "p": query, "pg": "1", "psz": str(min(max_results, 60)), "qt": "product", "sort": "curp", "isTestStoreIncluded": "0", "spaceId": 2092111218, "searchChain": "auction_pic_cb", "source": "pc"},
            "extensions": {"persistedQuery": {"version": 1, "sha256Hash": _GRAPHQL_HASH}},
        })

        async with primp.AsyncClient(
            impersonate=self._impersonate, impersonate_os="windows", timeout=self._timeout,
            headers={"content-type": "application/json", "origin": "https://tw.bid.yahoo.com", "referer": "https://tw.bid.yahoo.com/"},
        ) as client:
            with suppress(Exception):
                resp = await client.post(self._GRAPHQL_URL, content=payload)
                if resp.status_code == 200:
                    decoded = _graphql_decoder.decode(resp.content)
                    if decoded.data and decoded.data.get_uther:
                        return self._parse_hits(decoded.data.get_uther.hits, max_results, min_price, max_price, buy_now_only, prepared_keywords)
        return []

    async def _search_html(
        self, query: str, max_results: int, min_price: int, max_price: int, buy_now_only: bool, prepared_keywords: tuple[tuple[str, ...], ...] | None
    ) -> list[Product]:
        """Fallback: Search by parsing HTML."""
        from urllib.parse import quote

        url = f"{self._HTML_URL}?p={quote(query)}&clv=0&sort=curp"

        async with primp.AsyncClient(
            impersonate=self._impersonate, impersonate_os="windows", timeout=self._timeout, http2_only=True,
            headers={"accept": "text/html,application/xhtml+xml"},
        ) as client:
            with suppress(Exception):
                resp = await client.get(url)
                if resp.status_code != 200:
                    return []

                start_idx = resp.content.find(_ISOREDUX_START)
                if start_idx == -1:
                    return []
                start_idx += len(_ISOREDUX_START)
                if (end_idx := resp.content.find(_ISOREDUX_END, start_idx)) == -1:
                    return []

                data = _html_decoder.decode(resp.content[start_idx:end_idx])
                return self._parse_hits(data.search.ecsearch.hits, max_results, min_price, max_price, buy_now_only, prepared_keywords)
        return []

    def _parse_hits(
        self, hits: list[_YahooAuctionProduct], max_results: int, min_price: int, max_price: int, buy_now_only: bool, prepared_keywords: tuple[tuple[str, ...], ...] | None
    ) -> list[Product]:
        """Parse product hits into Product list."""
        products: list[Product] = []
        seen_ids: set[str] = set()

        for item in hits:
            if len(products) >= max_results:
                break

            if not item.ec_title or not item.ec_item_url:
                continue
            if item.ec_productid in seen_ids:
                continue

            # Determine price based on buy_now_only flag
            if buy_now_only:
                if item.ec_buyprice <= 0:
                    continue
                price = item.ec_buyprice
            else:
                price = item.ec_buyprice if item.ec_buyprice > 0 else item.ec_price

            if price <= 0 or (min_price and price < min_price) or (max_price and price > max_price):
                continue
            if not matches_keywords(item.ec_title.lower(), prepared_keywords):
                continue

            seen_ids.add(item.ec_productid)
            products.append(Product(name=item.ec_title, price=int(price), url=item.ec_item_url, platform=self.name))

        return products
