"""PChome platform implementation."""

import asyncio
from urllib.parse import quote

import msgspec
import never_primp as primp

from price_compare.models import Product
from price_compare.platforms.base import BasePlatform


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

    def __init__(
        self,
        impersonate: str | None = "chrome_142",
        timeout: float = 30.0,
    ) -> None:
        self._impersonate = impersonate
        self._timeout = timeout

    async def search(self, query: str, max_results: int = 50) -> list[Product]:
        """Search products on PChome with concurrent page fetching."""
        encoded_query = quote(query)
        per_page = 20
        # API already sorts by price, so 1-2 pages is enough
        pages_needed = min((max_results + per_page - 1) // per_page, 2)

        async with primp.AsyncClient(
            impersonate=self._impersonate,
            timeout=self._timeout,
            http2_only=True,
        ) as client:
            # Build URLs for all pages
            urls = [f"{self._BASE_URL}?q={encoded_query}&page={p}&sort=prc/ac" for p in range(1, pages_needed + 1)]

            # Fetch all pages concurrently
            tasks = [client.get(url) for url in urls]
            responses = await asyncio.gather(*tasks, return_exceptions=True)

            # Parse all responses
            products: list[Product] = []
            for resp in responses:
                if isinstance(resp, BaseException) or resp.status_code != 200:
                    continue
                data = _decoder.decode(resp.content)
                for item in data.prods:
                    if len(products) >= max_results:
                        break
                    products.append(
                        Product(
                            name=item.name,
                            price=item.price,
                            url=self._PRODUCT_URL.format(item.Id),
                            platform=self.name,
                        )
                    )
                if len(products) >= max_results:
                    break

        return products[:max_results]
