"""Yahoo Shopping (Yahoo購物中心) platform implementation."""

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
_GRAPHQL_HASH = "2a0c2518414ba006e0a42b5bc640a76bbb533e99a336d55027f6e3b4a796aafd"

# HTML fallback markers
_ISOREDUX_START = b'<script id="isoredux-data" type="mime/invalid">'
_ISOREDUX_END = b"</script>"


class _YahooProduct(msgspec.Struct):
    """Yahoo Shopping product from API response."""

    ec_title: str = ""
    ec_price: float = 0.0
    ec_item_url: str = ""
    ec_productid: str = ""


class _GetUther(msgspec.Struct):
    """GraphQL getUther response."""

    hits: list[_YahooProduct] = []


class _GraphQLData(msgspec.Struct, rename="camel"):
    """GraphQL data wrapper."""

    get_uther: _GetUther | None = None


class _GraphQLResponse(msgspec.Struct):
    """GraphQL response structure."""

    data: _GraphQLData | None = None


# HTML fallback structures
class _EcSearch(msgspec.Struct):
    hits: list[_YahooProduct] = []


class _Search(msgspec.Struct):
    ecsearch: _EcSearch = msgspec.field(default_factory=_EcSearch)


class _IsoreduxData(msgspec.Struct):
    search: _Search = msgspec.field(default_factory=_Search)


_graphql_decoder = msgspec.json.Decoder(_GraphQLResponse, strict=False)
_html_decoder = msgspec.json.Decoder(_IsoreduxData, strict=False)


class YahooShoppingPlatform(BasePlatform[list]):
    """Yahoo Shopping (Yahoo購物中心) platform."""

    __slots__ = ("_impersonate", "_timeout")

    name = "yahoo_shopping"
    _GRAPHQL_URL = "https://graphql.ec.yahoo.com/graphql"
    _HTML_URL = "https://tw.buy.yahoo.com/search/product"
    # sort=price is the site's price-ascending sort; the pipeline confirms the order.

    def __init__(
        self,
        impersonate: "IMPERSONATE | None" = "chrome_142",
        timeout: float = 30.0,
    ) -> None:
        self._impersonate = impersonate
        self._timeout = timeout

    async def _fetch(self, query: str, max_results: int, *, include_auction: bool = False) -> list | None:
        """Fetch hits, GraphQL first and the rendered page as a fallback."""
        return await self._fetch_graphql(query, max_results) or await self._fetch_html(query)

    async def _fetch_graphql(self, query: str, max_results: int) -> list | None:
        """Fetch hits from the GraphQL endpoint."""
        payload = msgspec.json.encode(
            {
                "variables": {
                    "property": "shopping",
                    "cid": "0",
                    "clv": "0",
                    "p": query,
                    "pg": "1",
                    "psz": str(min(max_results, 60)),
                    "qt": "product",
                    "sort": "price",
                    "isTestStoreIncluded": "0",
                    "spaceId": 2092115029,
                    "searchChain": "shopping_cb",
                    "source": "pc",
                },
                "extensions": {"persistedQuery": {"version": 1, "sha256Hash": _GRAPHQL_HASH}},
            }
        )

        async with primp.AsyncClient(
            impersonate=self._impersonate,
            impersonate_os="windows",
            timeout=self._timeout,
            headers={"content-type": "application/json", "origin": "https://tw.buy.yahoo.com", "referer": "https://tw.buy.yahoo.com/"},
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
        async with primp.AsyncClient(
            impersonate=self._impersonate,
            impersonate_os="windows",
            timeout=self._timeout,
            http2_only=True,
            headers={"accept": "text/html,application/xhtml+xml"},
        ) as client:
            with suppress(Exception):
                resp = await client.get(f"{self._HTML_URL}?p={quote(query)}&sort=price")
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

    def _extract(self, payload: list) -> Iterator[Candidate]:
        """Read hits out of a response."""
        for item in payload:
            if not item.ec_item_url:
                continue
            # Unlike Yahoo Auction this property exposes no variant range - only
            # ec_listprice (the pre-discount price) and ec_price - so nothing to pass on.
            yield Candidate(id=item.ec_productid, name=item.ec_title, price=item.ec_price, url=item.ec_item_url)
