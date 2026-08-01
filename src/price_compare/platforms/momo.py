"""momo platform implementation."""

import asyncio
from collections.abc import Iterator
from contextlib import suppress
from typing import TYPE_CHECKING

import never_primp as primp

if TYPE_CHECKING:
    from never_primp import IMPERSONATE

from price_compare.platforms.base import BasePlatform, Candidate

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


class MomoPlatform(BasePlatform[list[dict]]):
    """momo shopping platform."""

    __slots__ = ("_impersonate", "_timeout")

    name = "momo"
    _API_URL = "https://apisearch.momoshop.com.tw/momoSearchCloud/moec/textSearch"
    _PRODUCT_URL = "https://www.momoshop.com.tw/goods/GoodsDetail.jsp?i_code={}"
    _PAGE_SIZE = 20
    _MAX_PAGES = 5

    def __init__(self, impersonate: "IMPERSONATE | None" = "chrome_142", timeout: float = 30.0) -> None:
        self._impersonate = impersonate
        self._timeout = timeout

    async def _fetch(self, query: str, max_results: int, *, include_auction: bool = False) -> list[dict] | None:
        """
        Fetch as many result pages as max_results needs, concurrently.

        The mobile API fixes its page at 20 items with no size parameter, so covering
        max_results means issuing that many requests.
        """
        pages = min(-(-max_results // self._PAGE_SIZE), self._MAX_PAGES)  # ceiling division

        async with primp.AsyncClient(
            impersonate=self._impersonate,
            impersonate_os="windows",
            timeout=self._timeout,
            http2_only=True,
            headers={"content-type": "application/json", "origin": "https://m.momoshop.com.tw", "referer": "https://m.momoshop.com.tw/"},
        ) as client:
            bodies: list[dict | None] = [None] * pages
            pending = list(range(pages))

            # Retry individual pages rather than discarding the set: a hole is not a
            # partial success, but refusing partials without retries leaves the whole
            # platform silent on a transient failure.
            for attempt in range(self.PAGE_ATTEMPTS):
                responses = await asyncio.gather(
                    *(client.post(self._API_URL, json=self._build_payload(query, i + 1)) for i in pending),
                    return_exceptions=True,
                )
                failed = []
                for index, resp in zip(pending, responses):
                    data = None
                    if not isinstance(resp, BaseException) and resp.status_code == 200:
                        with suppress(Exception):
                            data = resp.json()
                    if data and data.get("success"):
                        bodies[index] = data
                    else:
                        failed.append(index)

                if not failed:
                    break
                pending = failed
                if attempt + 1 == self.PAGE_ATTEMPTS:
                    return None
                await asyncio.sleep(self.PAGE_RETRY_DELAY)

        return [body for body in bodies if body is not None] or None

    def _extract(self, payload: list[dict]) -> Iterator[Candidate]:
        """Read goods out of each page body."""
        for data in payload:
            for item in (data.get("rtnSearchData") or {}).get("goodsInfoList") or []:
                goods_code, name = item.get("goodsCode"), item.get("goodsName")
                if not (goods_code and name):
                    continue
                yield Candidate(
                    id=goods_code,
                    name=name,
                    price=item.get("SALE_PRICE"),
                    url=self._PRODUCT_URL.format(goods_code),
                )

    def _build_payload(self, query: str, page: int) -> dict:
        """Build API request payload."""
        return {
            "host": _PAYLOAD_TEMPLATE["host"],
            "flag": _PAYLOAD_TEMPLATE["flag"],
            "data": {**_PAYLOAD_TEMPLATE["data"], "searchValue": query, "curPage": page},
        }
