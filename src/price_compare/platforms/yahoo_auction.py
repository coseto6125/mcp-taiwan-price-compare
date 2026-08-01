"""Yahoo Auction (Yahoo拍賣) platform implementation."""

import re
from collections.abc import Iterator
from contextlib import suppress
from typing import TYPE_CHECKING
from urllib.parse import quote

import msgspec
import never_primp as primp

if TYPE_CHECKING:
    from never_primp import IMPERSONATE

from price_compare.platforms.base import BasePlatform, Candidate

# GraphQL persisted query hash - may need update if Yahoo changes their frontend
_GRAPHQL_HASH = "9e8c95a7bd216439855a6dcb580387b180713a20260a89c26096fbe4dd30133f"

# HTML fallback markers
# Listing kinds that are not a product offered at the stated price. This is a C2C
# marketplace, so alongside goods it carries wanted ads (the buyer is the one posting),
# placeholders and auctions baiting with a $1 buy-now. The site exposes no field for
# any of them, so the seller's own wording is the only signal.
#
# Every marker here has to be a phrase that only a non-retail listing would use.
# Two earlier attempts were too broad and each was measured against live listings:
#   - bare 維修 / 訂製 / 客製化 / 收購 threw away 49 of 60 results for "維修工具" and
#     21 for "訂製 印章" - goods whose titles merely name what they are for.
#   - 徵求 / 出租 / 下標專區 / 運費專區 / 補差價 caught a curtain shop recruiting
#     advertising participants (徵求廣告戶), a shoebox for rented rooms (出租屋), a
#     free-shipping promotion (免運費專區) and a steel rack sold through a
#     訂製下標專區. Sellers use those words for ordinary goods.
_NON_RETAIL_MARKERS = re.compile(
    r"【徵】|求購|收購中|高價收"  # the poster is buying, not selling
    r"|請勿下標|勿下標|測試商品"  # placeholders and do-not-buy notices
    r"|訂金專[區場]"  # deposit-only entries
    r"|[1一]元起標|起標價"  # auctions baiting with a $1 buy-now
    r"|隨選贈|滿額贈"  # gift-with-purchase entries
)

_ISOREDUX_START = b'<script id="isoredux-data" type="mime/invalid">'
_ISOREDUX_END = b"</script>"


class _YahooAuctionProduct(msgspec.Struct):
    """Yahoo Auction product from API response."""

    ec_title: str = ""
    ec_price: float = 0.0
    ec_buyprice: float = 0.0
    ec_item_url: str = ""
    ec_productid: str = ""
    ec_max_price: str = ""


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


class YahooAuctionPlatform(BasePlatform[tuple[list, bool]]):
    """Yahoo Auction (Yahoo拍賣) platform."""

    __slots__ = ("_impersonate", "_timeout")

    name = "yahoo_auction"
    _GRAPHQL_URL = "https://graphql.ec.yahoo.com/graphql"
    _SITE_URL = "https://tw.bid.yahoo.com"
    _HTML_URL = "https://tw.bid.yahoo.com/search/auction/product"
    # sort=curp is the site's price-ascending sort; the pipeline confirms the order.

    def __init__(
        self,
        impersonate: "IMPERSONATE | None" = "chrome_142",
        timeout: float = 30.0,
    ) -> None:
        self._impersonate = impersonate
        self._timeout = timeout

    async def _fetch(self, query: str, max_results: int, *, include_auction: bool = False) -> tuple[list, bool] | None:
        """
        Fetch hits, GraphQL first and the rendered page as a fallback.

        Returns the hits alongside the buy-now-only flag, because which price field a
        hit exposes depends on it and `_extract` has no other way to know.
        """
        buy_now_only = not include_auction
        hits = await self._fetch_graphql(query, max_results) or await self._fetch_html(query)
        return (hits, buy_now_only) if hits else None

    async def _fetch_graphql(self, query: str, max_results: int) -> list | None:
        """Fetch hits from the GraphQL endpoint."""
        payload = msgspec.json.encode(
            {
                "variables": {
                    "property": "auction",
                    "cid": "0",
                    "clv": "0",
                    "p": query,
                    "pg": "1",
                    "psz": str(min(max_results, 60)),
                    "qt": "product",
                    "sort": "curp",
                    "isTestStoreIncluded": "0",
                    "spaceId": 2092111218,
                    "searchChain": "auction_pic_cb",
                    "source": "pc",
                },
                "extensions": {"persistedQuery": {"version": 1, "sha256Hash": _GRAPHQL_HASH}},
            }
        )

        async with primp.AsyncClient(
            impersonate=self._impersonate,
            impersonate_os="windows",
            timeout=self._timeout,
            headers={"content-type": "application/json", "origin": "https://tw.bid.yahoo.com", "referer": "https://tw.bid.yahoo.com/"},
        ) as client:
            with suppress(Exception):
                resp = await client.post(self._GRAPHQL_URL, content=payload)
                if resp.status_code == 200:
                    decoded = _graphql_decoder.decode(resp.content)
                    if decoded.data and decoded.data.get_uther:
                        return decoded.data.get_uther.hits
        return None

    async def _fetch_html(self, query: str) -> list | None:
        """Fall back to the isoredux blob embedded in the rendered search page."""
        url = f"{self._HTML_URL}?p={quote(query)}&clv=0&sort=curp"

        async with primp.AsyncClient(
            impersonate=self._impersonate,
            impersonate_os="windows",
            timeout=self._timeout,
            http2_only=True,
            headers={"accept": "text/html,application/xhtml+xml"},
        ) as client:
            with suppress(Exception):
                resp = await client.get(url)
                if resp.status_code != 200:
                    return None

                start = resp.content.find(_ISOREDUX_START)
                if start == -1:
                    return None
                start += len(_ISOREDUX_START)
                if (end := resp.content.find(_ISOREDUX_END, start)) == -1:
                    return None
                return _html_decoder.decode(resp.content[start:end]).search.ecsearch.hits
        return None

    def _extract(self, payload: tuple[list, bool]) -> Iterator[Candidate]:
        """
        Read hits out of a response.

        Buy-now-only keeps listings that carry a buy price; otherwise a bid-only
        listing falls back to its current bid.
        """
        hits, buy_now_only = payload
        for item in hits:
            if not item.ec_item_url or _NON_RETAIL_MARKERS.search(item.ec_title):
                continue
            if buy_now_only:
                if item.ec_buyprice <= 0:
                    continue
                price = item.ec_buyprice
            else:
                price = item.ec_buyprice if item.ec_buyprice > 0 else item.ec_price

            # Some hits carry a site-relative path instead of an absolute URL.
            url = item.ec_item_url if item.ec_item_url.startswith("http") else f"{self._SITE_URL}{item.ec_item_url}"
            yield Candidate(id=item.ec_productid, name=item.ec_title, price=price, url=url, price_max=item.ec_max_price or None)
