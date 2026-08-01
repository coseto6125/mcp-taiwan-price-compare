"""生活市集 (buy123.com.tw) platform implementation."""

import re
from contextlib import suppress
from typing import TYPE_CHECKING

import msgspec
import never_primp as primp

if TYPE_CHECKING:
    from never_primp import IMPERSONATE

from price_compare.models import Product
from price_compare.platforms.base import BasePlatform
from price_compare.utils import KeywordGroups, matches_keywords, prepare_keyword_groups

_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)


class Buy123Platform(BasePlatform):
    """生活市集 (buy123.com.tw) platform."""

    __slots__ = ("_impersonate", "_timeout")

    name = "buy123"
    _SEARCH_URL = "https://www.buy123.com.tw/search"
    _PRODUCT_URL = "https://www.buy123.com.tw/site/sku/{display_id}"

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
        """
        Search products on 生活市集 (buy123.com.tw).

        The search page is a server-rendered Next.js page (no public JSON API):
        results live in the `__NEXT_DATA__` script tag, capped at ~40 items per
        page with no working pagination or price-sort query params found.
        """
        async with primp.AsyncClient(
            impersonate=self._impersonate,
            impersonate_os="windows",
            timeout=self._timeout,
            http2_only=True,
            headers={"accept": "text/html", "referer": "https://www.buy123.com.tw/"},
        ) as client:
            resp = await client.get(self._SEARCH_URL, params={"q": query})
            if resp.status_code != 200:
                return []

            html = resp.text
            if not (match := _NEXT_DATA_RE.search(html)):
                return []

            data = None
            with suppress(msgspec.DecodeError):
                data = msgspec.json.decode(match.group(1))
            if not data:
                return []

            with suppress(KeyError, TypeError):
                commodities = data["props"]["pageProps"]["searchCommodities"]["commodities"]
                return self._parse_products(
                    commodities, max_results, min_price, max_price, prepare_keyword_groups(require_words)
                )
            return []

    def _parse_products(
        self,
        commodities: list[dict],
        max_results: int,
        min_price: int,
        max_price: int,
        prepared_keywords: tuple[tuple[str, ...], ...] | None,
    ) -> list[Product]:
        """Parse search commodities into a Product list."""
        results: list[Product] = []
        seen_ids: set[str] = set()

        for item in commodities:
            item_id = item.get("id")
            if not item_id or item_id in seen_ids:
                continue

            if not (name := item.get("name")) or not (display_id := item.get("display_id")):
                continue
            if (price_raw := item.get("price")) is None:
                continue
            try:
                price = int(str(price_raw).replace(",", ""))
            except ValueError:
                continue
            if price <= 0:
                continue
            if (min_price and price < min_price) or (max_price and price > max_price):
                continue
            if not matches_keywords(name.lower(), prepared_keywords):
                continue

            seen_ids.add(item_id)
            results.append(
                Product(name=name, price=price, url=self._PRODUCT_URL.format(display_id=display_id), platform=self.name)
            )

        # The Next.js payload carries the whole result page and offers no price sort,
        # so ordering here turns an arbitrary page slice into the cheapest matches.
        results.sort(key=lambda p: p.price)
        return results[:max_results]
