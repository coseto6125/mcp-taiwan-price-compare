"""Rakuten Taiwan (樂天市場) platform implementation."""

from collections.abc import Iterator
from contextlib import suppress
from typing import TYPE_CHECKING

import msgspec
import never_primp as primp

if TYPE_CHECKING:
    from never_primp import IMPERSONATE

from price_compare.platforms.base import BasePlatform, Candidate

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

# itemHits is an enum, not a number. Asking for a bucket bigger than needed costs
# latency (Twenty 0.51s, Sixty 0.55s, Hundred 0.66s), and a hard-coded Sixty would
# silently cap results below the 100 the service asks for.
_ITEM_HITS = ((20, "Twenty"), (40, "Forty"), (60, "Sixty"))


def _item_hits(max_results: int) -> str:
    """Return the smallest itemHits bucket that covers max_results."""
    return next((name for size, name in _ITEM_HITS if max_results <= size), "Hundred")


class RakutenPlatform(BasePlatform[list[dict]]):
    """Rakuten Taiwan (樂天市場) platform."""

    __slots__ = ("_impersonate", "_timeout")

    name = "rakuten"
    # sort: LowestPrice picks WHICH items come back, but the response leads with
    # sponsored placements (measured: 720, 2160, 740, 1080, 1160 ahead of the $1
    # listings), so the pipeline orders it rather than trusting the parameter name.
    _GRAPHQL_URL = "https://www.rakuten.com.tw/graphql"

    def __init__(self, impersonate: "IMPERSONATE | None" = "chrome_142", timeout: float = 30.0) -> None:
        self._impersonate = impersonate
        self._timeout = timeout

    async def _fetch(self, query: str, max_results: int, *, include_auction: bool = False) -> list[dict] | None:
        """Request the GraphQL search endpoint and return its item entries."""
        payload = {
            "operationName": "fetchSearchPageResults",
            "query": _GRAPHQL_QUERY,
            "variables": {"parameters": {"itemHits": _item_hits(max_results), "sort": "LowestPrice", "keyword": query}},
        }

        async with primp.AsyncClient(
            impersonate=self._impersonate,
            impersonate_os="windows",
            timeout=self._timeout,
            http2_only=True,
            headers={
                "content-type": "application/json",
                "origin": "https://www.rakuten.com.tw",
                "referer": "https://www.rakuten.com.tw/search/",
            },
        ) as client:
            with suppress(Exception):
                resp = await client.post(self._GRAPHQL_URL, json=payload)
                if resp.status_code != 200:
                    return None

                data = msgspec.json.decode(resp.content)
                search_page = (data.get("data") or {}).get("searchPage") or {}
                return (search_page.get("result") or {}).get("items")
        return None

    def _extract(self, payload: list[dict]) -> Iterator[Candidate]:
        """Read items out of the decoded response."""
        for item in payload:
            item_id, name, url = item.get("itemId"), item.get("itemName"), item.get("itemUrl")
            if not (item_id and name and url):
                continue
            yield Candidate(id=str(item_id), name=name, price=(item.get("itemPrice") or {}).get("min"), url=url)
