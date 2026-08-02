"""Base platform interface."""

import asyncio
import heapq
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Iterable, Sequence
from operator import attrgetter
from typing import NamedTuple, Protocol

from price_compare.models import Product
from price_compare.utils import KeywordGroups, calc_search_multiplier, matches_keywords, parse_price, prepare_keyword_groups


class PageResponse(Protocol):
    """
    The part of a client's response that the paged fetch relies on.

    Read-only members, because the client's own Response exposes the body as a lazy
    property and a mutable attribute here would not accept it.
    """

    @property
    def status_code(self) -> int: ...

    @property
    def content(self) -> bytes: ...

    def json(self) -> object: ...


# One page request, ready to send. A thunk rather than a URL because the paged
# adapters differ in method: ETMall and PChome GET a URL, momo POSTs a per-page body.
type PageRequest = Callable[[], Awaitable[PageResponse]]
# Reads a page body out of a 200 response, or None when the response is unusable and
# the page should be retried. momo answers 200 with {"success": false}.
type PageReader = Callable[[PageResponse], object]


def read_content(resp: PageResponse) -> bytes:
    """Default page reader: the response body as it arrived."""
    return resp.content


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
    # Set only when the site reports a price range for the listing. Then `price` is the
    # floor across variants, not what the named product costs - see the pipeline.
    price_max: object = None


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

    # How far a listing's variants may spread before its floor stops representing
    # the named product. See the spread check in `build`.
    MAX_VARIANT_SPREAD = 8

    # How many candidates to request, regardless of how many the caller wants back.
    # Filtering happens after fetching, so sizing the request to max_results starves
    # it: asking Rakuten for 20 and then applying a keyword filter returned 2 products
    # where a full pool yields 20. Adapters that page fetch enough pages to cover this.
    POOL_SIZE = 100

    # Ceiling for the widened pool a keyword filter asks for. Past this the extra
    # pages cost more than the matches they turn up.
    MAX_POOL_SIZE = 200

    # Paged adapters retry individual pages rather than discarding the whole set.
    PAGE_ATTEMPTS = 3
    PAGE_RETRY_DELAY = 0.3

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
        payload = await self._fetch(query, self._pool_for(require_words), include_auction=include_auction)
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
        # Keyed by id so a repeated listing keeps its cheapest entry. Sites interleave
        # sponsored copies of the same product ahead of the plain one, so keeping
        # whichever arrived first would let their ordering pick the price.
        cheapest: dict[str, Product] = {}

        for candidate in candidates:
            if not candidate.id or not (name := candidate.name.strip()):
                continue
            if (price := parse_price(candidate.price)) is None or price <= 0:
                continue
            # A listing priced as a range quotes its cheapest variant. That is a fair
            # price when the variants are the same kind of thing (a $740-$776 coffee pot
            # differing only by mains voltage) and a wrong one when the floor is an
            # accessory on a listing named for something else (a $1-$7,621 office chair,
            # a $1 single cup on a listing named for a $140 fifty-pack).
            #
            # Measured over 206 range-priced listings from Rakuten and Yahoo Auction, the
            # spread splits at a valley between 6x and 10x: 143 sit below 6x and are
            # genuine variants, 56 sit above 10x and are not, and only 7 fall between.
            # The cut goes in that gap.
            if (ceiling := parse_price(candidate.price_max)) is not None and ceiling >= price * self.MAX_VARIANT_SPREAD:
                continue
            if (min_price and price < min_price) or (max_price and price > max_price):
                continue
            if not matches_keywords(name.lower(), prepared):
                continue

            if (previous := cheapest.get(candidate.id)) is None or price < previous.price:
                cheapest[candidate.id] = Product(name=name, price=price, url=candidate.url, platform=self.name)

        # Always ordered here rather than trusting a site's sort parameter. Coupang's
        # salePriceAsc and Rakuten's LowestPrice both interleave sponsored placements
        # (measured: 16 inversions and a 720/2160/740 lead-in respectively), so a
        # platform that declared itself pre-sorted would hand back an arbitrary slice
        # the moment its ranking changed. Sorting ~100 items costs microseconds.
        return heapq.nsmallest(max_results, cheapest.values(), key=attrgetter("price"))

    def _pool_for(self, require_words: KeywordGroups) -> int:
        """
        How many candidates to request for a search with these filters.

        Each AND group roughly halves the pass rate, so a keyword filter needs a wider
        pool to still leave max_results behind. Adapters that page turn this into more
        pages; the ones that fetch a fixed page ignore anything above their own cap.
        """
        return min(self.POOL_SIZE * calc_search_multiplier(require_words), self.MAX_POOL_SIZE)

    async def _fetch_pages(self, requests: "Sequence[PageRequest]", read: PageReader = read_content) -> list | None:
        """
        Send every page request concurrently, retrying the ones that fail.

        A page fetch that quietly drops its failures looks like a complete result set
        with a hole in it, and when the missing page is the first one what comes back
        is not even the site's cheapest listings. Refusing a partial set is only usable
        with retries though: ETMall dropped a page often enough that all-or-nothing
        left it silent in 3 of 8 searches, and every one of those cleared on a retry.

        Args:
            requests: One thunk per page, in the order the bodies should come back.
            read: Turns a 200 response into a page body, or None to retry the page.

        Returns:
            Every page body in request order, or None if any page never arrived.
        """
        bodies: list = [None] * len(requests)
        pending = list(range(len(requests)))

        for attempt in range(self.PAGE_ATTEMPTS):
            responses = await asyncio.gather(*(requests[index]() for index in pending), return_exceptions=True)

            failed = []
            for index, resp in zip(pending, responses):
                body = None if isinstance(resp, BaseException) or resp.status_code != 200 else read(resp)
                if body is None:
                    failed.append(index)
                else:
                    bodies[index] = body

            if not failed:
                return [body for body in bodies if body is not None] or None
            pending = failed
            if attempt + 1 < self.PAGE_ATTEMPTS:
                await asyncio.sleep(self.PAGE_RETRY_DELAY)

        return None

    @abstractmethod
    async def _fetch(self, query: str, max_results: int, *, include_auction: bool = False) -> Payload | None:
        """Request the site and return its raw response, or None if it could not be read."""

    @abstractmethod
    def _extract(self, payload: Payload) -> Iterable[Candidate]:
        """Read candidates out of a response. Pure - no network, no filtering."""
