"""
Offline parser tests.

Every other test in this suite reaches its parser through a live request, so a site
outage and a broken parser produce the same red. These drive the same parsers from a
saved response instead: they fail only when the parsing itself breaks.

Coupang shipped a parser that returned zero products for months after that site moved to
Next.js, and no test caught it. Regenerate a fixture with tests/fixtures/README.md when a
site's markup changes on purpose - a diff there is the record of what changed.
"""

import pathlib

import pytest

from price_compare.models import Product
from price_compare.platforms.books import BooksPlatform
from price_compare.platforms.coupang import CoupangPlatform
from price_compare.platforms.uniprosperity import UniProsperityPlatform

FIXTURES = pathlib.Path(__file__).parent / "fixtures"

# platform class, fixture file, how many products the fixture holds
PARSERS = [
    (CoupangPlatform, "coupang_search.html", 6),
    (BooksPlatform, "books_search.html", 6),
    (UniProsperityPlatform, "uniprosperity_search.html", 8),
]
PARSER_IDS = [cls.name for cls, _, _ in PARSERS]
# Most tests derive their expectations from the fixture itself and only need the pair.
FIXTURES_ONLY = [(cls, fixture) for cls, fixture, _ in PARSERS]
CLASSES_ONLY = [cls for cls, _, _ in PARSERS]
# Same pages with one product's name rewritten to hold an escaped quote.
ESCAPED_QUOTE_FIXTURES = {"uniprosperity": "uniprosperity_escaped_quote.html", "books": "books_escaped_quote.html", "coupang": "coupang_escaped_quote.html"}


def parse(platform_cls, fixture: str, **kwargs) -> list[Product]:
    """
    Run a platform's parser over a saved response.

    The fixture is handed over exactly as the site sent it. Parsers unescape the values
    they capture, not the page, so pre-unescaping here would hide that.
    """
    content = (FIXTURES / fixture).read_text(encoding="utf-8")
    defaults = {"max_results": 100, "min_price": 0, "max_price": 0, "prepared_keywords": None}
    return platform_cls()._parse_products(content, **(defaults | kwargs))


@pytest.mark.parametrize(("platform_cls", "fixture", "expected"), PARSERS, ids=PARSER_IDS)
def test_parser_extracts_every_product_in_the_fixture(platform_cls, fixture: str, expected: int) -> None:
    """Test the parser finds each product block the fixture contains."""
    assert len(parse(platform_cls, fixture)) == expected


@pytest.mark.parametrize(("platform_cls", "fixture"), FIXTURES_ONLY, ids=PARSER_IDS)
def test_parser_fills_every_product_field(platform_cls, fixture: str) -> None:
    """Test each parsed product carries a name, a positive price, and an absolute URL."""
    products = parse(platform_cls, fixture)
    assert products
    assert all(p.name.strip() for p in products)
    assert all(p.price > 0 for p in products)
    assert all(p.url.startswith("https://") for p in products)
    assert all(p.platform == platform_cls.name for p in products)


@pytest.mark.parametrize(("platform_cls", "fixture"), FIXTURES_ONLY, ids=PARSER_IDS)
def test_parser_deduplicates_repeated_markup(platform_cls, fixture: str) -> None:
    """Test ids repeated by the page's own markup yield one product each."""
    products = parse(platform_cls, fixture)
    assert len({p.url for p in products}) == len(products)


@pytest.mark.parametrize(("platform_cls", "fixture"), FIXTURES_ONLY, ids=PARSER_IDS)
def test_parser_applies_price_bounds(platform_cls, fixture: str) -> None:
    """Test min_price and max_price drop products outside the range."""
    everything = parse(platform_cls, fixture)
    prices = sorted(p.price for p in everything)
    floor, ceiling = prices[1], prices[-2]

    assert all(p.price >= floor for p in parse(platform_cls, fixture, min_price=floor))
    assert all(p.price <= ceiling for p in parse(platform_cls, fixture, max_price=ceiling))
    assert parse(platform_cls, fixture, min_price=prices[-1] + 1) == []


@pytest.mark.parametrize(("platform_cls", "fixture"), FIXTURES_ONLY, ids=PARSER_IDS)
def test_parser_applies_keyword_groups(platform_cls, fixture: str) -> None:
    """Test require_words keeps only names matching one keyword from every group."""
    first = parse(platform_cls, fixture)[0]
    token = first.name.strip()[:2].lower()

    kept = parse(platform_cls, fixture, prepared_keywords=((token,),))
    assert kept
    assert all(token in p.name.lower() for p in kept)

    assert parse(platform_cls, fixture, prepared_keywords=(("zzz-no-such-product",),)) == []
    assert parse(platform_cls, fixture, prepared_keywords=((token,), ("zzz-no-such-product",))) == []


@pytest.mark.parametrize(("platform_cls", "fixture"), FIXTURES_ONLY, ids=PARSER_IDS)
def test_parser_honours_max_results(platform_cls, fixture: str) -> None:
    """Test truncation keeps the cheapest matches rather than an arbitrary slice."""
    everything = parse(platform_cls, fixture)
    cheapest_two = sorted(p.price for p in everything)[:2]
    assert sorted(p.price for p in parse(platform_cls, fixture, max_results=2)) == cheapest_two


@pytest.mark.parametrize("platform_cls", CLASSES_ONLY, ids=PARSER_IDS)
def test_parser_returns_empty_for_unrecognised_markup(platform_cls) -> None:
    """Test a page whose markup no longer matches yields nothing instead of raising."""
    assert platform_cls()._parse_products("<html><body>404</body></html>", 100, 0, 0, None) == []


@pytest.mark.parametrize("platform_cls", CLASSES_ONLY, ids=PARSER_IDS)
def test_parser_keeps_names_containing_an_escaped_quote(platform_cls) -> None:
    """
    Test a name holding &quot; survives instead of being cut at the embedded quote.

    Unescaping the whole page before matching a quote-delimited attribute turns &quot;
    into a bare quote that closes the match early, so `SONY 27&quot;LCD` parses as `SONY 27`.
    """
    products = parse(platform_cls, ESCAPED_QUOTE_FIXTURES[platform_cls.name])
    assert products
    assert any('"' in p.name for p in products), "no product carried the embedded quote"
    assert all("顯示器" in p.name for p in products if '"' in p.name)
