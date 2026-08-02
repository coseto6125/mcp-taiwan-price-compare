"""
Refresh every parser fixture from the live sites.

Run from the repo root when a site changes its markup or response shape on purpose:

    .venv/bin/python -m tests.fixtures.regenerate

For each file it writes, it reads the file back through the same loader and parser the
tests use and prints the two counts they pin - `PARSERS` for the HTML fixtures and
`EXPECTED` for the payloads, both in `tests/test_parsers.py`. Update those tables to
match, or the parser tests will fail - deliberately, so a fixture cannot drift without
someone noticing.

Nothing is written when the fresh response yields fewer products than the fixture already
on disk: a revamp that breaks a delimiter is exactly when this script gets run, and
overwriting a good fixture with a degraded one would destroy the record of what changed.
The floor is measured by reading the committed file with the *current* parser, so a
deliberate parser change that retires the old fixture drops the floor to zero and lets
the replacement through.
"""

import asyncio
import pathlib
import re
from contextlib import suppress
from typing import NamedTuple

import msgspec

from price_compare.platforms import books, coupang, uniprosperity
from price_compare.platforms.base import BasePlatform
from price_compare.service import PriceCompareService
from tests.test_parsers import PAYLOAD_LOADERS

OUT = pathlib.Path(__file__).parent
QUERY = "咖啡"

# How much of the page before the first product to keep. Enough to show what the markup
# around a result looks like, small enough to stay committable.
HEAD_BYTES = 2000

# The name given to one product in each `*_escaped_quote.html` fixture, and the two
# things `test_parser_keeps_names_containing_an_escaped_quote` looks for in what the
# parser reads back: a bare quote, on a name carrying this word and no other.
ESCAPED_QUOTE_NAME = "SONY 27&quot;顯示器 特仕版"
ESCAPED_QUOTE_MARKER = "顯示器"

# name -> (product-block delimiter, that adapter's own name pattern, blocks to keep).
# Both come from the adapter rather than being restated here: a delimiter that drifted
# from the parser's would produce a fixture the parser cannot read.
HTML_SOURCES = {
    "coupang": (coupang._PRODUCT_DELIMITER, coupang._NAME_PATTERN, 6),
    "books": (books._PRODUCT_DELIMITER, books._NAME_PATTERN, 6),
    "uniprosperity": (uniprosperity._TILE_DELIMITER, uniprosperity._NAME_PATTERN, 8),
}

# Adapters whose payload is a list of page bodies rather than a list of products.
PAGED = {"etmall", "pchome", "momo"}
# Of those, the ones whose page body is raw bytes rather than a decoded object.
RAW_BODY_PAGES = {"etmall", "pchome"}
JSON_SOURCES = (
    "costco",
    "pxbox",
    "ruten",
    "buy123",
    "pcone",
    "rakuten",
    "momo",
    "pchome",
    "etmall",
    "yahoo_auction",
    "yahoo_shopping",
)


def _trim(name: str, payload):
    """
    Cut a payload down to something small enough to commit.

    Costco keeps a deliberate mix: its price-ascending page leads with in-warehouse-only
    entries that carry no price, and the fixture holds two of those so the tests also
    prove the pipeline drops them.
    """
    if name == "yahoo_auction":
        return (payload[0][:6], payload[1])
    if name in PAGED:
        return payload[:1]
    if name == "costco":
        priced, priceless = [], []
        for item in payload:
            (priced if (item.get("price") or {}).get("value") else priceless).append(item)
        return priceless[:2] + priced[:6]
    return payload[:6]


def encode(name: str, payload: object) -> bytes:
    """
    Serialise an adapter's payload in the shape `PAYLOAD_LOADERS` reads back.

    This is the inverse of that table, so every write is verified by loading the file
    again rather than by trusting the two to stay in step.
    """
    if name == "yahoo_auction":
        hits, buy_now_only = payload
        return msgspec.json.encode({"hits": [msgspec.to_builtins(h) for h in hits], "buy_now_only": buy_now_only})
    if name in RAW_BODY_PAGES:
        return msgspec.json.encode([body.decode() for body in payload])
    return msgspec.json.encode([msgspec.to_builtins(item) for item in payload])


def with_escaped_quote(blocks: list[str], name_pattern: re.Pattern) -> list[str] | None:
    """
    Rewrite the first product's name to one carrying an escaped quote.

    The name is replaced through the adapter's own pattern, so the fixture holds the
    quote in whichever attribute or element that parser actually reads.
    """
    if (match := name_pattern.search(blocks[1])) is None:
        return None
    start, end = match.span(1)
    return [blocks[0], blocks[1][:start] + ESCAPED_QUOTE_NAME + blocks[1][end:], *blocks[2:]]


def parse_counts(platform: BasePlatform, payload) -> tuple[int, int]:
    """Return how many candidates a payload yields and how many survive the pipeline."""
    candidates = list(platform._extract(payload))
    return len(candidates), len(platform.build(iter(candidates)))


class PageCheck(NamedTuple):
    """One HTML fixture, read back through its own parser before anything is written."""

    filename: str
    content: str
    candidates: int
    products: int
    # Why this page must not replace the fixture it would overwrite, or None if it may.
    reason: str | None


def read_text(path: pathlib.Path) -> str:
    """Load an HTML fixture the way the tests do."""
    return path.read_text(encoding="utf-8")


def committed_products(platform: BasePlatform, path: pathlib.Path, load) -> int:
    """
    How many products the fixture already on disk yields, or 0 when there is none.

    Read with the current parser, so a parser change that retires the old fixture leaves
    no floor to clear - only a degraded response is held back, not an intended rewrite.
    """
    if not path.exists():
        return 0
    with suppress(Exception):
        return len(platform.build(platform._extract(load(path))))
    return 0


def inspect_page(platform: BasePlatform, filename: str, content: str, floor: int) -> PageCheck:
    """
    Parse a page the way the tests will and decide whether it can be committed.

    Parsing to something is not enough for the escaped-quote variant: every HTML
    `_extract` drops a block that is missing a field, so if the rewritten block is the
    one dropped, the other blocks still parse and the fixture would be written with the
    quote nowhere in it. The checks below are the assertions
    `test_parser_keeps_names_containing_an_escaped_quote` makes, so a fixture that would
    fail in CI is refused here instead.
    """
    candidates = list(platform._extract(content))
    products = platform.build(iter(candidates))
    reason = None

    if not candidates:
        reason = "parses to nothing"
    elif len(products) < floor:
        reason = f"only {len(products)} products against the {floor} the committed fixture holds"
    elif filename.endswith("_escaped_quote.html"):
        quoted = [p.name for p in products if '"' in p.name]
        if not any(ESCAPED_QUOTE_MARKER in name for name in quoted):
            reason = "the rewritten name did not survive parsing"
        elif not all(ESCAPED_QUOTE_MARKER in name for name in quoted):
            reason = "another product name carries a quote, which the test forbids"

    return PageCheck(filename, content, len(candidates), len(products), reason)


async def refresh_html(platform: BasePlatform, delimiter: str, name_pattern: re.Pattern, keep: int) -> None:
    """
    Refresh one HTML fixture and the escaped-quote variant derived from it.

    Both files are written or neither: the variant is defined as the search page with
    one name rewritten, so shipping a fresh page beside a stale variant would recreate
    exactly the drift that pairing them removed.
    """
    body = await platform._fetch(QUERY, platform.POOL_SIZE)
    if body is None:
        print(f"{platform.name:34} fetch failed, left as-is")
        return

    parts = body.split(delimiter)
    # Strictly more than `keep`, so the last kept block ends at the next delimiter
    # instead of running to the end of the page - Coupang's tail alone is ~800KB.
    if len(parts) - 1 <= keep:
        print(f"{platform.name:34} only {len(parts) - 1} product blocks on the page, left as-is")
        return

    blocks = [parts[0][-HEAD_BYTES:], *parts[1 : keep + 1]]
    if (quoted := with_escaped_quote(blocks, name_pattern)) is None:
        print(f"{platform.name:34} the name pattern matched no name to rewrite, both pages left as-is")
        return

    checks = [
        inspect_page(platform, filename, content, committed_products(platform, OUT / filename, read_text))
        for filename, content in (
            (f"{platform.name}_search.html", delimiter.join(blocks)),
            (f"{platform.name}_escaped_quote.html", delimiter.join(quoted)),
        )
    ]
    if blocked := [check for check in checks if check.reason]:
        for check in blocked:
            print(f"{check.filename:34} {check.reason}")
        print(f"{platform.name:34} both pages left as-is")
        return

    for check in checks:
        (OUT / check.filename).write_text(check.content, encoding="utf-8")
        print(f"{check.filename:34} {check.candidates} candidates, {check.products} products")


async def refresh_payload(platform: BasePlatform, name: str) -> None:
    """Refresh one JSON payload fixture."""
    payload = await platform._fetch(QUERY, platform.POOL_SIZE)
    if payload is None:
        print(f"{name:34} fetch failed, left as-is")
        return

    # Parsed back through the loader the tests use, before anything is written: the
    # counts printed have to be the ones the file will produce, and a payload that
    # round-trips to nothing must not replace a working fixture.
    load = PAYLOAD_LOADERS[name]
    blob = encode(name, _trim(name, payload))
    filename = f"{name}_payload.json"
    candidates, products = parse_counts(platform, load(blob))
    floor = committed_products(platform, OUT / filename, lambda path: load(path.read_bytes()))

    if not candidates:
        print(f"{filename:34} the trimmed payload parses to nothing, left as-is")
        return
    if products < floor:
        print(f"{filename:34} only {products} products against the {floor} the committed fixture holds, left as-is")
        return

    (OUT / filename).write_bytes(blob)
    print(f"{filename:34} {candidates} candidates, {products} products")


async def main() -> None:
    """Refresh every fixture and report what each parser reads back out of it."""
    service = PriceCompareService()
    try:
        for name, (delimiter, name_pattern, keep) in HTML_SOURCES.items():
            await refresh_html(service.platforms[name], delimiter, name_pattern, keep)
        for name in JSON_SOURCES:
            await refresh_payload(service.platforms[name], name)
    finally:
        await service.aclose()


if __name__ == "__main__":
    asyncio.run(main())
