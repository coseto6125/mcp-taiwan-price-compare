"""PChome pcone 松果購物 platform implementation."""

from contextlib import suppress
from typing import TYPE_CHECKING

import msgspec
import never_primp as primp

if TYPE_CHECKING:
    from never_primp import IMPERSONATE

from price_compare.models import Product
from price_compare.platforms.base import BasePlatform
from price_compare.utils import KeywordGroups, matches_keywords, prepare_keyword_groups


class PconePlatform(BasePlatform):
    """松果購物 (pcone.com.tw) platform."""

    __slots__ = ("_client", "_impersonate", "_timeout")

    name = "pcone"
    _SEARCH_URL = "https://webapi.pcone.com.tw/api/products/search"
    # The API host (webapi.pcone.com.tw) only serves requests carrying an
    # Origin/Referer from the storefront; it 302-redirects to "/" otherwise.
    _REFERER = "https://pcone.com.tw/search"
    _ORIGIN = "https://pcone.com.tw"

    def __init__(self, impersonate: "IMPERSONATE | None" = "chrome_142", timeout: float = 30.0) -> None:
        self._impersonate = impersonate
        self._timeout = timeout
        self._client: primp.AsyncClient | None = None

    def _get_client(self) -> "primp.AsyncClient":
        """
        Return a client whose connection is reused across searches.

        Cloudflare routes this host to a Singapore edge, so its round trip is ~0.2s
        against ~0.07s for the other platforms, and a fresh TCP+TLS handshake per
        search costs about 0.4s. Measured over randomised paired runs: 2.42s with a
        per-call client versus 2.00s reusing one. The other platforms show no such
        gain and are left constructing a client per call.
        """
        if self._client is None:
            self._client = primp.AsyncClient(
                impersonate=self._impersonate,
                impersonate_os="windows",
                timeout=self._timeout,
                http2_only=True,
                pool_idle_timeout=300,
                headers={
                    "accept": "application/json",
                    "content-type": "application/json",
                    "referer": self._REFERER,
                    "origin": self._ORIGIN,
                },
            )
        return self._client

    async def search(
        self,
        query: str,
        max_results: int = 100,
        min_price: int = 0,
        max_price: int = 0,
        require_words: KeywordGroups = None,
        **_: object,
    ) -> list[Product]:
        """Search products on 松果購物."""
        # The API has no relevance/price sort param (empirically verified: a
        # "sort" field is silently ignored). count=100 mirrors the fixed
        # candidate pool other platforms fetch before filtering down.
        body = {"count": 100, "page": 1, "seed": None, "kw": query}

        with suppress(Exception):
            resp = await self._get_client().post(self._SEARCH_URL, json=body)
            if resp.status_code != 200:
                return []

            data = None
            with suppress(msgspec.DecodeError):
                data = msgspec.json.decode(resp.content)
            if not data or data.get("status") != "SUCCESS" or not (payload := data.get("data")):
                return []
            if not (products := payload.get("products")):
                return []

            return self._parse_products(products, max_results, min_price, max_price, prepare_keyword_groups(require_words))
        return []

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
        seen_ids: set[str] = set()

        for item in products:
            display_id = item.get("display_id")
            if not display_id or display_id in seen_ids:
                continue

            if not (name := item.get("name")) or not (url := item.get("link_url")):
                continue
            if (price_raw := item.get("price")) is None:
                continue

            try:
                price = int(str(price_raw).replace(",", ""))
            except ValueError:
                continue

            if price <= 0 or (min_price and price < min_price) or (max_price and price > max_price):
                continue
            if not matches_keywords(name.lower(), prepared_keywords):
                continue

            seen_ids.add(display_id)
            results.append(Product(name=name, price=price, url=url, platform=self.name))

        # The API returns an unsorted candidate pool and offers no price sort,
        # so ordering here turns an arbitrary page slice into the cheapest matches.
        results.sort(key=lambda p: p.price)
        return results[:max_results]
