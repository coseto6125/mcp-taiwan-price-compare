"""Costco Taiwan (好市多) platform implementation."""

from contextlib import suppress
from typing import TYPE_CHECKING

import msgspec
import never_primp as primp

if TYPE_CHECKING:
    from never_primp import IMPERSONATE

from price_compare.models import Product
from price_compare.platforms.base import BasePlatform
from price_compare.utils import KeywordGroups, matches_keywords, prepare_keyword_groups


class CostcoPlatform(BasePlatform):
    """Costco Taiwan (好市多) platform."""

    __slots__ = ("_impersonate", "_timeout")

    name = "costco"
    _SEARCH_URL = "https://www.costco.com.tw/rest/v2/taiwan/products/search"
    _BASE_URL = "https://www.costco.com.tw"

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
        """Search products on Costco Taiwan."""
        params = {
            "query": query,
            "fields": "FULL",
            "lang": "zh_TW",
            "curr": "TWD",
            # Server-side price sort keeps the query intact (same totalResults as
            # relevance) and reaches cheap items that rank past the first page,
            # which a client-side sort of one relevance page would miss. It leads
            # with in-warehouse-only items that carry no price at all, so entries
            # without a price value are dropped below.
            "sort": "price-asc",
            "pageSize": "100",
        }

        async with primp.AsyncClient(
            impersonate=self._impersonate,
            impersonate_os="windows",
            timeout=self._timeout,
            http2_only=True,
            headers={"accept": "application/json", "referer": "https://www.costco.com.tw/search"},
        ) as client:
            resp = await client.get(self._SEARCH_URL, params=params)
            if resp.status_code != 200:
                return []

            data = None
            with suppress(msgspec.DecodeError):
                data = msgspec.json.decode(resp.content)
            if not data or not (products := data.get("products")):
                return []

            return self._parse_products(products, max_results, min_price, max_price, prepare_keyword_groups(require_words))

    def _parse_products(
        self,
        products: list[dict],
        max_results: int,
        min_price: int,
        max_price: int,
        prepared_keywords: tuple[tuple[str, ...], ...] | None,
    ) -> list[Product]:
        """Parse product search results into a Product list."""
        results: list[Product] = []
        seen_codes: set[str] = set()

        for item in products:
            if len(results) >= max_results:
                break

            code = item.get("code")
            if not code or code in seen_codes:
                continue

            if not (name := item.get("name")) or not (url := item.get("url")):
                continue
            if not (price_obj := item.get("price")) or (price_value := price_obj.get("value")) is None:
                continue

            # price_value comes off an untyped dict, so a non-numeric entry would raise
            # here rather than skip the product the way every other guard in this loop does.
            try:
                price = int(price_value)
            except (TypeError, ValueError):
                continue

            if price <= 0 or (min_price and price < min_price) or (max_price and price > max_price):
                continue
            if not matches_keywords(name.lower(), prepared_keywords):
                continue

            seen_codes.add(code)
            results.append(Product(name=name, price=price, url=f"{self._BASE_URL}{url}", platform=self.name))

        return results
