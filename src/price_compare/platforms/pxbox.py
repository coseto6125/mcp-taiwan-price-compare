"""PXBox (全聯全電商) platform implementation."""

from contextlib import suppress
from typing import TYPE_CHECKING

import msgspec
import never_primp as primp

if TYPE_CHECKING:
    from never_primp import IMPERSONATE

from price_compare.models import Product
from price_compare.platforms.base import BasePlatform
from price_compare.utils import KeywordGroups, matches_keywords, prepare_keyword_groups


class _PxboxProduct(msgspec.Struct):
    """PXBox product from API response."""

    id: int = 0
    product_name: str = ""
    sale_price: float = 0.0
    is_sold_out: bool = False
    is_ad: bool = False


class _PxboxData(msgspec.Struct):
    """PXBox search response data payload."""

    product_list: list[_PxboxProduct] = []


class _PxboxResponse(msgspec.Struct):
    """PXBox search response structure."""

    code: str = ""
    data: _PxboxData | None = None


_decoder = msgspec.json.Decoder(_PxboxResponse, strict=False)


class PxboxPlatform(BasePlatform):
    """PXBox (全聯全電商, PX Mart's nationwide-shipping storefront) platform."""

    __slots__ = ("_impersonate", "_timeout")

    name = "pxbox"
    _SEARCH_URL = "https://api-pxbox.es.pxmart.com.tw/app/2.0/spu/single_search"
    _SITE_URL = "https://pxbox.es.pxmart.com.tw"
    _SUCCESS_CODE = "0000"

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
        """Search products on PXBox."""
        prepared_keywords = prepare_keyword_groups(require_words)
        payload = msgspec.json.encode(
            {
                "search_setting_type": 2,
                "keyword": query,
                # sort_type 3 (price) + sort_order 1 (ascending) - verified empirically,
                # sort_order 0 falls back to relevance and 2 is descending.
                "sort_type": 3,
                "sort_order": 1,
                "page_index": 1,
                # Fixed pool rather than max_results: sold-out and ad entries are
                # dropped after the fact, so a small request would come back empty.
                "page_size": 100,
                "filters": [],
            }
        )

        async with primp.AsyncClient(
            impersonate=self._impersonate,
            impersonate_os="windows",
            timeout=self._timeout,
            headers={"content-type": "application/json", "origin": self._SITE_URL, "referer": f"{self._SITE_URL}/"},
        ) as client:
            with suppress(Exception):
                resp = await client.post(self._SEARCH_URL, content=payload)
                if resp.status_code != 200:
                    return []

                decoded = _decoder.decode(resp.content)
                if decoded.code != self._SUCCESS_CODE or decoded.data is None:
                    return []

                return self._parse_products(decoded.data.product_list, max_results, min_price, max_price, prepared_keywords)
        return []

    def _parse_products(
        self,
        items: list[_PxboxProduct],
        max_results: int,
        min_price: int,
        max_price: int,
        prepared_keywords: tuple[tuple[str, ...], ...] | None,
    ) -> list[Product]:
        """Parse product entries into Product list."""
        products: list[Product] = []
        seen_ids: set[int] = set()

        for item in items:
            if len(products) >= max_results:
                break

            if not item.product_name or item.id in seen_ids:
                continue
            # Sold-out items and ad placements are not genuine cheapest-price matches.
            if item.is_sold_out or item.is_ad:
                continue

            price = item.sale_price
            if price <= 0 or (min_price and price < min_price) or (max_price and price > max_price):
                continue
            if not matches_keywords(item.product_name.lower(), prepared_keywords):
                continue

            seen_ids.add(item.id)
            products.append(Product(name=item.product_name, price=int(price), url=f"{self._SITE_URL}/product/{item.id}", platform=self.name))

        return products
