"""Rakuten Taiwan (樂天市場) platform implementation."""

from contextlib import suppress
from typing import TYPE_CHECKING

import msgspec
import never_primp as primp

if TYPE_CHECKING:
    from never_primp import IMPERSONATE

from price_compare.models import Product
from price_compare.platforms.base import BasePlatform
from price_compare.utils import KeywordGroups, matches_keywords, prepare_keyword_groups

_GRAPHQL_QUERY = """
query fetchSearchPageResults($parameters: GspInputType!) {
  searchPage(parameters: $parameters) {
    result {
      items {
        itemId
        itemName
        itemUrl
        itemPrice { min }
      }
    }
  }
}
"""


class RakutenPlatform(BasePlatform):
    """Rakuten Taiwan (樂天市場) platform."""

    __slots__ = ("_impersonate", "_timeout")

    name = "rakuten"
    _GRAPHQL_URL = "https://www.rakuten.com.tw/graphql"

    def __init__(self, impersonate: "IMPERSONATE | None" = "chrome_142", timeout: float = 30.0) -> None:
        self._impersonate = impersonate
        self._timeout = timeout

    async def search(
        self,
        query: str,
        max_results: int = 100,
        min_price: int = 0,
        max_price: int = 0,
        include_keywords: KeywordGroups = None,
        **_: object,
    ) -> list[Product]:
        """Search products on Rakuten Taiwan."""
        payload = {
            "operationName": "fetchSearchPageResults",
            "query": _GRAPHQL_QUERY,
            "variables": {"parameters": {"itemHits": "Sixty", "sort": "LowestPrice", "keyword": query}},
        }

        async with primp.AsyncClient(
            impersonate=self._impersonate,
            impersonate_os="windows",
            timeout=self._timeout,
            http2_only=True,
            headers={"content-type": "application/json", "origin": "https://www.rakuten.com.tw", "referer": "https://www.rakuten.com.tw/search/"},
        ) as client:
            resp = await client.post(self._GRAPHQL_URL, json=payload)
            if resp.status_code != 200:
                return []

            data = None
            with suppress(msgspec.DecodeError):
                data = msgspec.json.decode(resp.content)
            if not data:
                return []

            # Navigate to items
            if not (search_page := data.get("data", {}).get("searchPage")):
                return []
            if not (items := search_page.get("result", {}).get("items")):
                return []

            return self._parse_items(items, max_results, min_price, max_price, prepare_keyword_groups(include_keywords))

    def _parse_items(
        self,
        items: list[dict],
        max_results: int,
        min_price: int,
        max_price: int,
        prepared_keywords: tuple[tuple[str, ...], ...] | None,
    ) -> list[Product]:
        """Parse GraphQL response items into Product list."""
        products: list[Product] = []
        seen_ids: set[str] = set()

        for item in items:
            if len(products) >= max_results:
                break

            item_id = item.get("itemId", "")
            if item_id in seen_ids:
                continue

            if not (name := item.get("itemName")) or not (item_url := item.get("itemUrl")):
                continue
            if not (price_obj := item.get("itemPrice")) or not (price_min := price_obj.get("min")):
                continue

            price = int(price_min)
            if price <= 0 or (min_price and price < min_price) or (max_price and price > max_price):
                continue
            if not matches_keywords(name.lower(), prepared_keywords):
                continue

            seen_ids.add(item_id)
            products.append(Product(name=name, price=price, url=item_url, platform=self.name))

        return products
