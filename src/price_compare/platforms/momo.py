"""momo platform implementation using textSearch API."""

import asyncio
from typing import TYPE_CHECKING, Any

import never_primp as primp

if TYPE_CHECKING:
    from never_primp import IMPERSONATE

from price_compare.models import Product
from price_compare.platforms.base import BasePlatform


class MomoPlatform(BasePlatform):
    """momo shopping platform."""

    __slots__ = ("_impersonate", "_timeout")

    name = "momo"
    _API_URL = "https://apisearch.momoshop.com.tw/momoSearchCloud/moec/textSearch"
    _PRODUCT_URL = "https://www.momoshop.com.tw/goods/GoodsDetail.jsp?i_code={}"
    _PAGE_SIZE = 20  # API returns 20 items per page

    def __init__(
        self,
        impersonate: "IMPERSONATE | None" = "chrome_142",
        timeout: float = 30.0,
    ) -> None:
        self._impersonate = impersonate
        self._timeout = timeout

    def _build_payload(self, query: str, page: int) -> dict[str, Any]:
        """Build API request payload."""
        return {
            "host": "ecmobile",
            "flag": "searchEngine",
            "data": {
                "searchValue": query,
                "curPage": page,
                "maxPage": 30,
                "cateLevel": -1,
                "serviceCode": "MT01",
                "platform": 16,
                "has3P": "Y",
                # Default filters
                "NAM": "N",
                "china": "N",
                "cp": "N",
                "first": "N",
                "freeze": "N",
                "prefere": "N",
                "stockYN": "N",
                "superstore": "N",
                "threeHours": "N",
                "tomorrow": "N",
                "tvshop": "N",
                "video": "N",
                "cycle": "N",
                "cod": "N",
                "superstorePay": "N",
                "moCoinFeedback": "N",
                "superstoreFree": "N",
                "discount": "N",
                "isBrandSeriesPage": False,
                "isShowAdShop": False,
                "curRecommendedWordsCnt": 0,
            },
        }

    async def search(self, query: str, max_results: int = 50) -> list[Product]:
        """Search products on momo using textSearch API."""
        pages_needed = min((max_results + self._PAGE_SIZE - 1) // self._PAGE_SIZE, 3)

        async with primp.AsyncClient(
            impersonate=self._impersonate,
            impersonate_os="windows",
            timeout=self._timeout,
            http2_only=True,
            headers={
                "content-type": "application/json",
                "accept": "application/json, text/plain, */*",
                "origin": "https://m.momoshop.com.tw",
                "referer": "https://m.momoshop.com.tw/",
            },
        ) as client:
            # Fetch all pages concurrently
            tasks = [
                client.post(self._API_URL, json=self._build_payload(query, p))
                for p in range(1, pages_needed + 1)
            ]
            responses = await asyncio.gather(*tasks, return_exceptions=True)

            # Parse all responses
            products: list[Product] = []
            seen_ids: set[str] = set()

            for resp in responses:
                if isinstance(resp, BaseException) or resp.status_code != 200:
                    continue

                try:
                    data = resp.json()
                    if not data.get("success"):
                        continue
                    goods_list = data.get("rtnSearchData", {}).get("goodsInfoList", [])
                except Exception:
                    continue

                for item in goods_list:
                    if len(products) >= max_results:
                        break
                    goods_code = item.get("goodsCode")
                    if not goods_code or goods_code in seen_ids:
                        continue

                    price = item.get("SALE_PRICE")
                    name = item.get("goodsName")
                    if not price or not name:
                        continue

                    seen_ids.add(goods_code)
                    products.append(
                        Product(
                            name=name,
                            price=int(price),
                            url=self._PRODUCT_URL.format(goods_code),
                            platform=self.name,
                        )
                    )

        return sorted(products, key=lambda p: p.price)[:max_results]
