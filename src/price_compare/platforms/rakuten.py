"""Rakuten Taiwan (樂天市場) platform implementation."""

from typing import TYPE_CHECKING
from urllib.parse import quote

import msgspec
import never_primp as primp

if TYPE_CHECKING:
    from never_primp import IMPERSONATE

from price_compare.models import Product
from price_compare.platforms.base import BasePlatform

_ITEMS_MARKER = '"items":['


def _extract_json_array(text: str, start_marker: str) -> str | None:
    """Extract a JSON array from text using bracket counting."""
    start_idx = text.find(start_marker)
    if start_idx == -1:
        return None

    # Start after the marker (excluding the '[')
    array_start = start_idx + len(start_marker) - 1

    bracket_count = 0
    in_string = False
    escape_next = False

    for i, c in enumerate(text[array_start:], start=array_start):
        if escape_next:
            escape_next = False
            continue
        if c == "\\":
            escape_next = True
            continue
        if c == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == "[":
            bracket_count += 1
        elif c == "]":
            bracket_count -= 1
            if bracket_count == 0:
                return text[array_start : i + 1]

    return None


class RakutenPlatform(BasePlatform):
    """Rakuten Taiwan (樂天市場) platform."""

    __slots__ = ("_impersonate", "_timeout")

    name = "rakuten"
    _SEARCH_URL = "https://www.rakuten.com.tw/search/{}/"

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
        encoded_query = quote(query)
        # s=2 = sort by price low to high
        url = f"{self._SEARCH_URL.format(encoded_query)}?s=2"

        async with primp.AsyncClient(
            impersonate=self._impersonate,
            impersonate_os="windows",
            timeout=self._timeout,
            http2_only=True,
            headers={
                "accept": "text/html,application/xhtml+xml",
                "accept-language": "zh-TW,zh;q=0.9",
            },
        ) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return []

            # Extract items JSON array
            items_json = _extract_json_array(resp.text, _ITEMS_MARKER)
            if not items_json:
                return []

            try:
                items = msgspec.json.decode(items_json)
            except msgspec.DecodeError:
                return []

            # Pre-process keywords for case-insensitive matching
            keywords_lower = (
                [kw.lower() for kw in required_keywords] if required_keywords else None
            )

            products: list[Product] = []
            seen_urls: set[str] = set()

            for item in items:
                if len(products) >= max_results:
                    break

                name = item.get("itemName", "")
                item_url = item.get("itemUrl", "")
                price_obj = item.get("itemPrice")

                if not name or not item_url or not price_obj:
                    continue

                # Get minimum price (float in API response)
                price_min = price_obj.get("min", 0)
                if not price_min or price_min <= 0:
                    continue
                price = int(price_min)

                # Skip duplicates
                if item_url in seen_urls:
                    continue
                seen_urls.add(item_url)

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
