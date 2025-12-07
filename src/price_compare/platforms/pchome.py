"""PChome platform implementation."""

import asyncio
from contextlib import suppress
from typing import TYPE_CHECKING
from urllib.parse import quote

import msgspec
import never_primp as primp

if TYPE_CHECKING:
    from never_primp import IMPERSONATE

from price_compare.models import Product
from price_compare.platforms.base import BasePlatform
from price_compare.utils import KeywordGroups, calc_search_multiplier, matches_keywords, prepare_keyword_groups


class _PChomeProd(msgspec.Struct):
    """PChome product from API response."""

    Id: str
    name: str
    price: int


class _PChomeResponse(msgspec.Struct):
    """PChome API response."""

    prods: list[_PChomeProd] = []


_decoder = msgspec.json.Decoder(_PChomeResponse)


class PChomePlatform(BasePlatform):
    """PChome 24h shopping platform."""

    __slots__ = ("_impersonate", "_timeout")

    name = "pchome"
    _BASE_URL = "https://ecshweb.pchome.com.tw/search/v3.3/all/results"
    _PRODUCT_URL = "https://24h.pchome.com.tw/prod/{}"
    _PAGE_SIZE = 20

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
        **_: object,
    ) -> list[Product]:
        """Search products on PChome."""
        prepared_keywords = prepare_keyword_groups(require_words)
        adjusted_max = max_results * calc_search_multiplier(require_words)
        pages_needed = min(-(-adjusted_max // self._PAGE_SIZE), 5)  # max 5 pages

        async with primp.AsyncClient(
            impersonate=self._impersonate,
            timeout=self._timeout,
            http2_only=True,
        ) as client:
            urls = [f"{self._BASE_URL}?q={quote(query)}&page={p}&sort=prc/ac" for p in range(1, pages_needed + 1)]
            responses = await asyncio.gather(*[client.get(url) for url in urls], return_exceptions=True)

            return self._parse_responses(responses, max_results, min_price, max_price, prepared_keywords)

    def _parse_responses(
        self,
        responses: list,
        max_results: int,
        min_price: int,
        max_price: int,
        prepared_keywords: tuple[tuple[str, ...], ...] | None,
    ) -> list[Product]:
        """Parse API responses into Product list."""
        products: list[Product] = []

        for resp in responses:
            if isinstance(resp, BaseException) or resp.status_code != 200:
                continue

            with suppress(msgspec.DecodeError):
                data = _decoder.decode(resp.content)

                for item in data.prods:
                    if len(products) >= max_results:
                        return products

                    # Combined filter
                    if (min_price and item.price < min_price) or (max_price and item.price > max_price):
                        continue
                    if not matches_keywords(item.name.lower(), prepared_keywords):
                        continue

                    products.append(Product(name=item.name, price=item.price, url=self._PRODUCT_URL.format(item.Id), platform=self.name))

        return products
