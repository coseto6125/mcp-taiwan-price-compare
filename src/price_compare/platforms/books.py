"""博客來 (books.com.tw) platform implementation."""

import html
import re
from contextlib import suppress
from typing import TYPE_CHECKING
from urllib.parse import quote

import never_primp as primp

if TYPE_CHECKING:
    from never_primp import IMPERSONATE

from price_compare.models import Product
from price_compare.platforms.base import BasePlatform
from price_compare.utils import KeywordGroups, matches_keywords, prepare_keyword_groups

# Search results are server-rendered; each result lives in one grid cell, distinct
# from the "floated-btn-wrap" recommendation footer that reuses the same item ids.
_PRODUCT_DELIMITER = '<div class="table-td" id="prod-itemlist-'
_ID_PATTERN = re.compile(r'^([^"]+)"')
_NAME_PATTERN = re.compile(r'title="([^"]+)"')
# 優惠價 may carry a discount-percent <b> before the actual price; the percent tag
# is never immediately followed by "元", so the non-greedy match skips past it.
_PRICE_PATTERN = re.compile(r"優惠價:.*?<b>([\d,]+)</b>\s*元")


class BooksPlatform(BasePlatform):
    """博客來 (books.com.tw) online bookstore."""

    __slots__ = ("_impersonate", "_timeout")

    name = "books"
    # sort/8 sorts by price ascending (verified empirically against relevance order).
    _SEARCH_URL = "https://search.books.com.tw/search/query/cat/all/sort/8/key/{}"
    _PRODUCT_URL = "https://www.books.com.tw/products/{}"

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
        """Search products on 博客來."""
        url = self._SEARCH_URL.format(quote(query))
        prepared_keywords = prepare_keyword_groups(require_words)

        async with primp.AsyncClient(
            impersonate=self._impersonate,
            impersonate_os="windows",
            timeout=self._timeout,
            follow_redirects=True,
        ) as client:
            # 博客來 resets connections outright when it throttles a client, so the
            # transport error has to be absorbed the same way a non-200 would be.
            with suppress(Exception):
                resp = await client.get(url)
                if resp.status_code != 200:
                    return []

                return self._parse_products(
                    resp.text, max_results, min_price, max_price, prepared_keywords
                )
        return []

    def _parse_products(
        self,
        content: str,
        max_results: int,
        min_price: int,
        max_price: int,
        prepared_keywords: tuple[tuple[str, ...], ...] | None,
    ) -> list[Product]:
        """Parse HTML content into Product list."""
        products: list[Product] = []
        seen_ids: set[str] = set()

        for block in content.split(_PRODUCT_DELIMITER)[1:]:
            if len(products) >= max_results:
                break

            if not (id_match := _ID_PATTERN.match(block)) or (product_id := id_match[1]) in seen_ids:
                continue
            # Unescape the captured value, never the page: a title holding &quot; would
            # otherwise become a bare quote and close the attribute match early, truncating it.
            if not (name_match := _NAME_PATTERN.search(block)) or not (name := html.unescape(name_match[1]).strip()):
                continue
            if not matches_keywords(name.lower(), prepared_keywords):
                continue
            if not (price_match := _PRICE_PATTERN.search(block)):
                continue

            with suppress(ValueError):
                price = int(price_match[1].replace(",", ""))
                if price <= 0 or (min_price and price < min_price) or (max_price and price > max_price):
                    continue

                seen_ids.add(product_id)
                products.append(
                    Product(
                        name=name,
                        price=price,
                        url=self._PRODUCT_URL.format(product_id),
                        platform=self.name,
                    )
                )

        return products
