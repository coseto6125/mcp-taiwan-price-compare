"""ETMall (東森購物) platform implementation."""

from typing import TYPE_CHECKING
from urllib.parse import quote

import msgspec
import never_primp as primp

if TYPE_CHECKING:
    from never_primp import IMPERSONATE

from price_compare.models import Product
from price_compare.platforms.base import BasePlatform


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

    def __init__(
        self,
        impersonate: "IMPERSONATE | None" = "chrome_142",
        timeout: float = 30.0,
    ) -> None:
        self._impersonate = impersonate
        self._timeout = timeout

    async def search(self, query: str, max_results: int = 50) -> list[Product]:
        """Search products on ETMall with price sorting (low to high)."""
        encoded_query = quote(query)
        url = (
            f"{self._SEARCH_URL}?"
            f"Keyword={encoded_query}&"
            f"SortType=4&"  # Price low to high
            f"PageSize={max_results}&"
            f"PageIndex=0"
        )

        async with primp.AsyncClient(
            impersonate=self._impersonate,
            impersonate_os="windows",
            timeout=self._timeout,
            headers={
                "accept": "application/json",
                "accept-language": "zh-TW,zh;q=0.9",
                "referer": "https://www.etmall.com.tw/",
            },
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

            products: list[Product] = []
            for item in data.search_product_result.products[:max_results]:
                try:
                    price = int(item.final_price.replace(",", ""))
                except ValueError:
                    continue

                if price <= 0:
                    continue

                product_url = f"https://www.etmall.com.tw{item.page_link}" if item.page_link else self._PRODUCT_URL.format(item.id)
                products.append(
                    Product(
                        name=item.title,
                        price=price,
                        url=product_url,
                        platform=self.name,
                    )
                )

            return products
