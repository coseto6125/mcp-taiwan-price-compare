"""Base platform interface."""

from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import NamedTuple

from price_compare.models import Product
from price_compare.utils import KeywordGroups, matches_keywords, parse_price, prepare_keyword_groups


class Candidate(NamedTuple):
    """
    One product as a site described it, before any filtering.

    `price` is whatever the site gave - an int, a float, or a string like "1,299" or
    "$1,299". Coercion happens once in the pipeline rather than in every adapter.
    """

    id: str
    name: str
    price: object
    url: str


class BasePlatform[Payload](ABC):
    """
    An e-commerce platform.

    Implementors supply two things: how to reach the site (`_fetch`) and how to read
    what came back (`_extract`). Everything a caller relies on - deduplication, price
    coercion, price bounds, keyword groups, ordering, truncation - lives here, so the
    rules cannot drift between platforms and a new adapter cannot forget one.

    Splitting the network call from the reading also means `_extract` is a pure
    function over a saved response, which is what `tests/test_parsers.py` drives.
    """

    __slots__ = ()

    name: str = "base"

    async def search(
        self,
        query: str,
        max_results: int = 100,
        min_price: int = 0,
        max_price: int = 0,
        require_words: KeywordGroups = None,
        include_auction: bool = False,
        **kwargs: object,
    ) -> list[Product]:
        """
        Search products by keyword.

        Args:
            query: Search keyword.
            max_results: Most products to return, applied after filtering.
            min_price: Lower price bound, 0 to disable.
            max_price: Upper price bound, 0 to disable.
            require_words: Keyword groups. A name must match at least one keyword from
                every group - AND between groups, OR within a group.
            include_auction: Include bid listings on the marketplaces that carry them.

        Returns:
            Matching products, cheapest first. Empty when the site failed or matched
            nothing; adapters never raise out of here.
        """
        payload = await self._fetch(query, max_results, include_auction=include_auction)
        if payload is None:
            return []
        return self.build(self._extract(payload), max_results, min_price, max_price, require_words)

    def build(
        self,
        candidates: Iterable[Candidate],
        max_results: int = 100,
        min_price: int = 0,
        max_price: int = 0,
        require_words: KeywordGroups = None,
    ) -> list[Product]:
        """Turn raw candidates into the products a caller asked for."""
        prepared = prepare_keyword_groups(require_words)
        products: list[Product] = []
        seen: set[str] = set()

        for candidate in candidates:
            if not candidate.id or candidate.id in seen or not (name := candidate.name.strip()):
                continue
            if (price := parse_price(candidate.price)) is None or price <= 0:
                continue
            if (min_price and price < min_price) or (max_price and price > max_price):
                continue
            if not matches_keywords(name.lower(), prepared):
                continue

            seen.add(candidate.id)
            products.append(Product(name=name, price=price, url=candidate.url, platform=self.name))

        # Always ordered here rather than trusting a site's sort parameter. Coupang's
        # salePriceAsc and Rakuten's LowestPrice both interleave sponsored placements
        # (measured: 16 inversions and a 720/2160/740 lead-in respectively), so a
        # platform that declared itself pre-sorted would hand back an arbitrary slice
        # the moment its ranking changed. Sorting ~100 items costs microseconds.
        products.sort(key=lambda p: p.price)
        return products[:max_results]

    @abstractmethod
    async def _fetch(self, query: str, max_results: int, *, include_auction: bool = False) -> Payload | None:
        """Request the site and return its raw response, or None if it could not be read."""

    @abstractmethod
    def _extract(self, payload: Payload) -> Iterable[Candidate]:
        """Read candidates out of a response. Pure - no network, no filtering."""
