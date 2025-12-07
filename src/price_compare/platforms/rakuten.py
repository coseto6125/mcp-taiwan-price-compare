"""Rakuten Taiwan (樂天市場) platform implementation using GraphQL API."""

from typing import TYPE_CHECKING

import msgspec
import never_primp as primp

if TYPE_CHECKING:
    from never_primp import IMPERSONATE

from price_compare.models import Product
from price_compare.platforms.base import BasePlatform

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
        max_results: int = 50,
        required_keywords: list[str] | None = None,
    ) -> list[Product]:
        """
        Search products on Rakuten Taiwan with price sorting (low to high).

        Args:
            query: Search query string
            max_results: Maximum number of results to return
            required_keywords: Product name must contain ALL these keywords (case-insensitive)
        """
        payload = {
            "operationName": "fetchSearchPageResults",
            "query": _GRAPHQL_QUERY,
            "variables": {
                "parameters": {
                    "itemHits": "Sixty",
                    "sort": "LowestPrice",
                    "keyword": query,
                }
            },
        }

        async with primp.AsyncClient(
            impersonate=self._impersonate,
            impersonate_os="windows",
            timeout=self._timeout,
            http2_only=True,
            headers={
                "content-type": "application/json",
                "accept": "application/json",
                "origin": "https://www.rakuten.com.tw",
                "referer": "https://www.rakuten.com.tw/search/",
            },
        ) as client:
            resp = await client.post(self._GRAPHQL_URL, json=payload)
            if resp.status_code != 200:
                return []

            try:
                data = msgspec.json.decode(resp.content)
            except msgspec.DecodeError:
                return []

            # Navigate to items
            search_page = data.get("data", {}).get("searchPage")
            if not search_page:
                return []
            items = search_page.get("result", {}).get("items", [])
            if not items:
                return []

            # Pre-process keywords for case-insensitive matching
            keywords_lower = (
                [kw.lower() for kw in required_keywords] if required_keywords else None
            )

            products: list[Product] = []
            seen_ids: set[str] = set()

            for item in items:
                if len(products) >= max_results:
                    break

                item_id = item.get("itemId", "")
                name = item.get("itemName", "")
                item_url = item.get("itemUrl", "")
                price_obj = item.get("itemPrice")

                if not name or not item_url or not price_obj:
                    continue

                # Get minimum price
                price_min = price_obj.get("min", 0)
                if not price_min or price_min <= 0:
                    continue
                price = int(price_min)

                # Skip duplicates
                if item_id in seen_ids:
                    continue
                seen_ids.add(item_id)

                # Filter by required keywords (all must match)
                if keywords_lower:
                    name_lower = name.lower()
                    if not all(kw in name_lower for kw in keywords_lower):
                        continue

                products.append(
                    Product(
                        name=name,
                        price=price,
                        url=item_url,
                        platform=self.name,
                    )
                )

            return products
