"""
Refresh every parser fixture from the live sites.

Run from the repo root when a site changes its markup or response shape on purpose:

    .venv/bin/python tests/fixtures/regenerate.py

It prints how many candidates each adapter reads back, which is what
`tests/test_parsers.py::EXPECTED` pins. Update that table to match, or the parser tests
will fail - deliberately, so a fixture cannot drift without someone noticing.
"""

import asyncio
import pathlib

import msgspec

from price_compare.service import PriceCompareService

OUT = pathlib.Path(__file__).parent
QUERY = "咖啡"

# name -> (url template, product-block delimiter, blocks to keep)
HTML_SOURCES = {
    "coupang": (
        "https://www.tw.coupang.com/np/search?q={q}&sorter=salePriceAsc&listSize=60",
        '<li class="ProductUnit_productUnit__',
        6,
    ),
    "books": (
        "https://search.books.com.tw/search/query/cat/all/sort/8/key/{q}",
        '<div class="table-td" id="prod-itemlist-',
        6,
    ),
    "uniprosperity": (
        "https://online.uni-prosperity.com.tw/on/demandware.store"
        "/Sites-Uniprosperity-Site/default/Search-UpdateGrid?q=q%3D{q}",
        '<a class="gtm-product-alink"',
        8,
    ),
}

# Adapters whose payload is a list of page bodies rather than a list of products.
PAGED = {"etmall", "pchome", "momo"}
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
        return (list(payload[0])[:6], payload[1])
    if name in PAGED:
        return payload[:1]
    if name == "costco":
        priced = [i for i in payload if (i.get("price") or {}).get("value")]
        priceless = [i for i in payload if not (i.get("price") or {}).get("value")]
        return priceless[:2] + priced[:6]
    return payload[:6]


def encode(name: str, payload: object) -> bytes:
    """Serialise an adapter's payload in a shape `PAYLOAD_LOADERS` can read back."""
    if name == "yahoo_auction":
        hits, buy_now_only = payload
        return msgspec.json.encode({"hits": [msgspec.to_builtins(h) for h in hits], "buy_now_only": buy_now_only})
    if name in ("etmall", "pchome"):
        return msgspec.json.encode([body.decode() for body in payload])
    return msgspec.json.encode([msgspec.to_builtins(item) for item in payload])


async def main() -> None:
    """Refresh every fixture and report what each adapter reads back."""
    from urllib.parse import quote

    import never_primp as primp

    async with primp.AsyncClient(impersonate="chrome_142", impersonate_os="windows", timeout=30.0, follow_redirects=True) as client:
        for name, (url, delimiter, keep) in HTML_SOURCES.items():
            body = (await client.get(url.format(q=quote(QUERY)))).text
            parts = body.split(delimiter)
            trimmed = parts[0][-2000:] + delimiter + delimiter.join(parts[1 : keep + 1])
            (OUT / f"{name}_search.html").write_text(trimmed, encoding="utf-8")
            print(f"{name:16} {len(parts) - 1} blocks on the page, kept {keep}")

    service = PriceCompareService()
    for name in JSON_SOURCES:
        platform = service.platforms[name]
        payload = await platform._fetch(QUERY, 100)
        if payload is None:
            print(f"{name:16} fetch failed, left as-is")
            continue

        payload = _trim(name, payload)

        (OUT / f"{name}_payload.json").write_bytes(encode(name, payload))
        extracted = list(platform._extract(payload))
        print(f"{name:16} EXPECTED = ({len(extracted)}, {len(platform.build(iter(extracted)))})")

    await service.aclose()


if __name__ == "__main__":
    asyncio.run(main())
