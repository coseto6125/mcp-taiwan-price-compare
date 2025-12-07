"""momo platform implementation."""

import asyncio
from contextlib import suppress
from operator import attrgetter
from typing import TYPE_CHECKING

import never_primp as primp

if TYPE_CHECKING:
    from never_primp import IMPERSONATE

from price_compare.models import Product
from price_compare.platforms.base import BasePlatform
from price_compare.utils import KeywordGroups, matches_keywords, prepare_keyword_groups

# Static payload template (filters that never change)
_PAYLOAD_TEMPLATE: dict = {
    "host": "ecmobile",
    "flag": "searchEngine",
    "data": {
        "maxPage": 30,
        "cateLevel": -1,
        "serviceCode": "MT01",
        "platform": 16,
        "has3P": "Y",
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


class MomoPlatform(BasePlatform):
    """momo shopping platform."""

    __slots__ = ("_impersonate", "_timeout")

    name = "momo"
    _API_URL = "https://apisearch.momoshop.com.tw/momoSearchCloud/moec/textSearch"
    _PRODUCT_URL = "https://www.momoshop.com.tw/goods/GoodsDetail.jsp?i_code={}"
    _PAGE_SIZE = 20

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
        """Search products on momo."""
        prepared_keywords = prepare_keyword_groups(include_keywords)
        pages_needed = min(-(-max_results // self._PAGE_SIZE), 3)  # Ceiling division

        async with primp.AsyncClient(
            impersonate=self._impersonate,
            impersonate_os="windows",
            timeout=self._timeout,
            http2_only=True,
            headers={"content-type": "application/json", "origin": "https://m.momoshop.com.tw", "referer": "https://m.momoshop.com.tw/"},
        ) as client:
            tasks = [client.post(self._API_URL, json=self._build_payload(query, p)) for p in range(1, pages_needed + 1)]
            responses = await asyncio.gather(*tasks, return_exceptions=True)

            products = self._parse_responses(responses, max_results, min_price, max_price, prepared_keywords)

        return sorted(products, key=attrgetter("price"))[:max_results]

    def _build_payload(self, query: str, page: int) -> dict:
        """Build API request payload."""
        return {"host": _PAYLOAD_TEMPLATE["host"], "flag": _PAYLOAD_TEMPLATE["flag"], "data": {**_PAYLOAD_TEMPLATE["data"], "searchValue": query, "curPage": page}}

    def _parse_responses(
        self,
        responses: list,
        max_results: int,
        min_price: int,
        max_price: int,
        prepared_keywords: tuple[tuple[str, ...], ...] | None,
    ) -> list[Product]:
        """Parse API responses into Product list."""
        products: list[Product] = []
        seen_ids: set[str] = set()

        for resp in responses:
            if isinstance(resp, BaseException) or resp.status_code != 200:
                continue

            data = None
            with suppress(Exception):
                data = resp.json()
            if not data or not data.get("success"):
                continue
            if not (goods_list := data.get("rtnSearchData", {}).get("goodsInfoList")):
                continue

            for item in goods_list:
                if len(products) >= max_results:
                    return products

                # Early exit: check seen_ids first (O(1) lookup)
                if not (goods_code := item.get("goodsCode")) or goods_code in seen_ids:
                    continue
                if not (name := item.get("goodsName")) or not (price := item.get("SALE_PRICE")):
                    continue

                # Parse price
                with suppress(ValueError):
                    price_int = int(str(price).replace("$", "").replace(",", ""))

                    # Combined price filter
                    if price_int <= 0 or (min_price and price_int < min_price) or (max_price and price_int > max_price):
                        continue
                    if not matches_keywords(name.lower(), prepared_keywords):
                        continue

                    seen_ids.add(goods_code)
                    products.append(Product(name=name, price=price_int, url=self._PRODUCT_URL.format(goods_code), platform=self.name))

        return products
