"""ETMall (東森購物) platform implementation."""

import asyncio
from collections.abc import Iterator
from contextlib import suppress
from typing import TYPE_CHECKING
from urllib.parse import quote

import msgspec
import never_primp as primp

if TYPE_CHECKING:
    from never_primp import IMPERSONATE

from price_compare.models import Product
from price_compare.platforms.base import BasePlatform, Candidate
from price_compare.utils import KeywordGroups, calc_search_multiplier


class _ProductData(msgspec.Struct, rename="camel"):
    """Product data from ETMall API."""

    id: int
    title: str
    final_price: str  # API returns price as string
    page_link: str | None = None


class _SearchProductResult(msgspec.Struct):
    """Search result container."""

    products: list[_ProductData] = []


class _SearchResponse(msgspec.Struct, rename="pascal"):
    """ETMall search API response."""

    search_product_result: _SearchProductResult | None = None


_decoder = msgspec.json.Decoder(_SearchResponse)


class ETMallPlatform(BasePlatform[list[bytes]]):
    """ETMall (東森購物) platform."""

    __slots__ = ("_impersonate", "_timeout")

    name = "etmall"
    # SortType=4 picks WHICH items come back (the cheapest), but pages are
    # fetched concurrently and concatenated, so the pipeline orders the result.
    _SEARCH_URL = "https://www.etmall.com.tw/Search/Get"
    _SITE_URL = "https://www.etmall.com.tw"
    _PRODUCT_URL = "https://www.etmall.com.tw/i/{}"
    _PAGE_SIZE = 40
    _MAX_PAGES = 5

    def __init__(self, impersonate: "IMPERSONATE | None" = "chrome_142", timeout: float = 30.0) -> None:
        self._impersonate = impersonate
        self._timeout = timeout

    async def search(
        self,
        query: str,
        max_results: int = 100,
        min_price: int = 0,
        max_price: int = 0,
        require_words: KeywordGroups = None,
        include_auction: bool = False,
        **kwargs: object,
    ) -> list[Product]:
        """Search products on ETMall, widening the request when a keyword filter is set."""
        # Each AND group roughly halves the pass rate, so ask for more before filtering.
        pool = min(max_results * calc_search_multiplier(require_words), 200)
        payload = await self._fetch(query, pool)
        if payload is None:
            return []
        return self.build(self._extract(payload), max_results, min_price, max_price, require_words)

    async def _fetch(self, query: str, max_results: int, *, include_auction: bool = False) -> list[bytes] | None:
        """
        Fetch as many result pages as max_results needs, concurrently.

        The site answers 400 to a PageSize much above _PAGE_SIZE, so asking for a big
        page in one request returns nothing at all. Because the service asks every
        platform for 100, that quietly kept ETMall out of every fan-out.
        """
        pages = min(-(-max_results // self._PAGE_SIZE), self._MAX_PAGES)  # ceiling division

        async with primp.AsyncClient(
            impersonate=self._impersonate,
            impersonate_os="windows",
            timeout=self._timeout,
            headers={"accept": "application/json", "referer": "https://www.etmall.com.tw/"},
        ) as client:
            urls = [
                f"{self._SEARCH_URL}?Keyword={quote(query)}&SortType=4&PageSize={self._PAGE_SIZE}&PageIndex={i}"
                for i in range(pages)
            ]
            responses = await asyncio.gather(*(client.get(url) for url in urls), return_exceptions=True)

        bodies = [r.content for r in responses if not isinstance(r, BaseException) and r.status_code == 200]
        return bodies or None

    def _extract(self, payload: list[bytes]) -> Iterator[Candidate]:
        """Read products out of each page body."""
        for body in payload:
            with suppress(msgspec.DecodeError):
                data = _decoder.decode(body)
                if not data.search_product_result:
                    continue
                for item in data.search_product_result.products:
                    url = f"{self._SITE_URL}{item.page_link}" if item.page_link else self._PRODUCT_URL.format(item.id)
                    yield Candidate(id=str(item.id), name=item.title, price=item.final_price, url=url)

