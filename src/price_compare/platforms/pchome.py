"""PChome platform implementation."""

from collections.abc import Iterator
from contextlib import suppress
from functools import partial
from typing import TYPE_CHECKING
from urllib.parse import quote

import msgspec
import never_primp as primp

if TYPE_CHECKING:
    from never_primp import IMPERSONATE

from price_compare.platforms.base import BasePlatform, Candidate


class _PChomeProd(msgspec.Struct):
    """PChome product from API response."""

    Id: str
    name: str
    price: int


class _PChomeResponse(msgspec.Struct):
    """PChome API response."""

    prods: list[_PChomeProd] = []


_decoder = msgspec.json.Decoder(_PChomeResponse)


class PChomePlatform(BasePlatform[list[bytes]]):
    """PChome 24h shopping platform."""

    __slots__ = ("_impersonate", "_timeout")

    name = "pchome"
    # sort=prc/ac picks WHICH items come back (the cheapest), but pages are
    # fetched concurrently and concatenated, so the pipeline orders the result.
    _BASE_URL = "https://ecshweb.pchome.com.tw/search/v3.3/all/results"
    _PRODUCT_URL = "https://24h.pchome.com.tw/prod/{}"
    # PChome marks add-on items with this prefix and exposes no field for them. They
    # cannot be bought on their own, so their price is not one a shopper can pay.
    _ADD_ON_MARKER = "【加價購】"
    _PAGE_SIZE = 20
    _MAX_PAGES = 5

    def __init__(self, impersonate: "IMPERSONATE | None" = "chrome_142", timeout: float = 30.0) -> None:
        self._impersonate = impersonate
        self._timeout = timeout

    async def _fetch(self, query: str, max_results: int, *, include_auction: bool = False) -> list[bytes] | None:
        """Fetch as many result pages as max_results needs, concurrently."""
        pages = min(-(-max_results // self._PAGE_SIZE), self._MAX_PAGES)  # ceiling division

        async with primp.AsyncClient(impersonate=self._impersonate, timeout=self._timeout, http2_only=True) as client:
            requests = [partial(client.get, f"{self._BASE_URL}?q={quote(query)}&page={p}&sort=prc/ac") for p in range(1, pages + 1)]
            return await self._fetch_pages(requests)

    def _extract(self, payload: list[bytes]) -> Iterator[Candidate]:
        """Read products out of each page body."""
        for body in payload:
            with suppress(msgspec.DecodeError):
                for item in _decoder.decode(body).prods:
                    if self._ADD_ON_MARKER in item.name:
                        continue
                    yield Candidate(
                        id=item.Id,
                        name=item.name,
                        price=item.price,
                        url=self._PRODUCT_URL.format(item.Id),
                    )
