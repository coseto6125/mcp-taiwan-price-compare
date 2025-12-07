"""ETMall (東森購物) platform implementation."""

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


class _ProductData(msgspec.Struct, rename="camel"):
    """Product data from ETMall API."""

    id: int
    title: str
    final_price: str  # API returns price as string
    page_link: str | None = None


class _SearchProductResult(msgspec.Struct):
    """Search result container."""

    products: list[_ProductData] = []


class _SearchResponse(msgspec.Struct, rename="pascal"):
    """ETMall search API response."""

    search_product_result: _SearchProductResult | None = None


_decoder = msgspec.json.Decoder(_SearchResponse)


class ETMallPlatform(BasePlatform):
    """ETMall (東森購物) platform."""

    __slots__ = ("_impersonate", "_timeout")

    name = "etmall"
    _SEARCH_URL = "https://www.etmall.com.tw/Search/Get"
    _PRODUCT_URL = "https://www.etmall.com.tw/i/{}"

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
        """Search products on ETMall."""
        adjusted_max = min(max_results * calc_search_multiplier(require_words), 200)
        url = f"{self._SEARCH_URL}?Keyword={quote(query)}&SortType=4&PageSize={adjusted_max}&PageIndex=0"
        prepared_keywords = prepare_keyword_groups(require_words)

        async with primp.AsyncClient(
            impersonate=self._impersonate,
            impersonate_os="windows",
            timeout=self._timeout,
            headers={"accept": "application/json", "referer": "https://www.etmall.com.tw/"},
        ) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return []

            try:
                data = _decoder.decode(resp.content)
            except msgspec.DecodeError:
                return []

            if not data.search_product_result:
                return []

            return self._parse_products(data.search_product_result.products, max_results, min_price, max_price, prepared_keywords)

    def _parse_products(
        self,
        items: list[_ProductData],
        max_results: int,
        min_price: int,
        max_price: int,
        prepared_keywords: tuple[tuple[str, ...], ...] | None,
    ) -> list[Product]:
        """Parse API response into Product list."""
        products: list[Product] = []
        for item in items:
            if len(products) >= max_results:
                break

            with suppress(ValueError):
                price = int(item.final_price.replace(",", ""))

                # Combined filter
                if price <= 0 or (min_price and price < min_price) or (max_price and price > max_price):
                    continue
                if not matches_keywords(item.title.lower(), prepared_keywords):
                    continue

                url = f"https://www.etmall.com.tw{item.page_link}" if item.page_link else self._PRODUCT_URL.format(item.id)
                products.append(Product(name=item.title, price=price, url=url, platform=self.name))

        return products
