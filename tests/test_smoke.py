"""
Daily smoke check: the aggregated search still returns products for an everyday keyword.

Runs from .github/workflows/smoke.yml every night. It is not a parser test; it only
proves the end-to-end path (network -> platform search -> aggregation) is alive.
"""

import contextlib

import pytest

from price_compare.service import PriceCompareService

pytestmark = [pytest.mark.live, pytest.mark.smoke]

# Sold on every platform all year round, so an empty result means the pipeline broke,
# not the catalogue.
STAPLE_KEYWORD = "衛生紙"


async def test_get_cheapest_staple_keyword_returns_matching_products() -> None:
    service = PriceCompareService()
    try:
        products = await service.get_cheapest(STAPLE_KEYWORD, top_n=20)
    finally:
        # A request that outlived PLATFORM_TIMEOUT can still hold its handle, so the close
        # raises "Already borrowed". Close hygiene belongs to test_service; here it must
        # not mask the search result.
        with contextlib.suppress(RuntimeError):
            await service.aclose()

    assert products, f"no products returned for {STAPLE_KEYWORD!r}"
    matching = [p for p in products if STAPLE_KEYWORD in p.name]
    assert matching, f"none of {len(products)} products mention {STAPLE_KEYWORD!r}: {[p.name for p in products]}"
    assert all(p.price > 0 and p.url for p in matching)
