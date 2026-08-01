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

import msgspec
import pytest

from price_compare.models import Product
from price_compare.platforms.base import Candidate
from price_compare.platforms.books import BooksPlatform
from price_compare.platforms.coupang import CoupangPlatform
from price_compare.platforms.pchome import PChomePlatform
from price_compare.platforms.rakuten import RakutenPlatform
from price_compare.platforms.uniprosperity import UniProsperityPlatform
from price_compare.platforms.yahoo_auction import YahooAuctionPlatform, _YahooAuctionProduct
from price_compare.service import PriceCompareService

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
    platform = platform_cls()
    return platform.build(platform._extract(content), **kwargs)


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

    kept = parse(platform_cls, fixture, require_words=[[token]])
    assert kept
    assert all(token in p.name.lower() for p in kept)

    assert parse(platform_cls, fixture, require_words=[["zzz-no-such-product"]]) == []
    assert parse(platform_cls, fixture, require_words=[[token], ["zzz-no-such-product"]]) == []


@pytest.mark.parametrize(("platform_cls", "fixture"), FIXTURES_ONLY, ids=PARSER_IDS)
def test_parser_honours_max_results(platform_cls, fixture: str) -> None:
    """Test truncation keeps the cheapest matches rather than an arbitrary slice."""
    everything = parse(platform_cls, fixture)
    cheapest_two = sorted(p.price for p in everything)[:2]
    assert sorted(p.price for p in parse(platform_cls, fixture, max_results=2)) == cheapest_two


@pytest.mark.parametrize("platform_cls", CLASSES_ONLY, ids=PARSER_IDS)
def test_parser_returns_empty_for_unrecognised_markup(platform_cls) -> None:
    """Test a page whose markup no longer matches yields nothing instead of raising."""
    platform = platform_cls()
    assert platform.build(platform._extract("<html><body>404</body></html>")) == []


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


# Every adapter, driven through the same seam with a hand-built payload. This does not
# replace the fixture tests above - it checks the contract the pipeline enforces for all
# 14 platforms, including the ones whose live response is JSON rather than HTML.
def test_pipeline_enforces_the_contract_for_every_platform() -> None:
    """Test build() applies the same rules whichever adapter supplied the candidates."""
    service = PriceCompareService()
    candidates = [
        Candidate(id="a", name="  便宜咖啡  ", price="1,200", url="https://example.test/a"),
        Candidate(id="b", name="貴咖啡", price=9_000.7, url="https://example.test/b"),
        Candidate(id="a", name="重複 id", price=10, url="https://example.test/dup"),
        Candidate(id="c", name="無價格", price=None, url="https://example.test/c"),
        Candidate(id="d", name="零元", price=0, url="https://example.test/d"),
        Candidate(id="e", name="價格不可解析", price="洽詢", url="https://example.test/e"),
        Candidate(id="f", name="   ", price=50, url="https://example.test/f"),
    ]

    for name, platform in service.platforms.items():
        products = platform.build(iter(candidates))

        assert [p.name for p in products] == ["便宜咖啡", "貴咖啡"], name
        assert [p.price for p in products] == [1200, 9000], name
        assert all(p.platform == name for p in products), name

        assert platform.build(iter(candidates), max_results=1)[0].price == 1200, name
        assert [p.price for p in platform.build(iter(candidates), min_price=2000)] == [9000], name
        assert [p.price for p in platform.build(iter(candidates), max_price=2000)] == [1200], name
        assert platform.build(iter(candidates), require_words=[["便宜"]])[0].name == "便宜咖啡", name
        assert platform.build(iter(candidates), require_words=[["不存在"]]) == [], name


def test_pipeline_orders_cheapest_first_regardless_of_input_order() -> None:
    """
    Test a site's own ranking cannot leak through as the returned order.

    Coupang and Rakuten both advertise a price-ascending sort and both interleave
    sponsored placements into it, so the pipeline never trusts the incoming order.
    """
    sponsored_first = [
        Candidate(id=str(i), name=f"商品{i}", price=price, url=f"https://example.test/{i}")
        for i, price in enumerate([720, 2160, 740, 1080, 1, 1, 1])
    ]
    products = CoupangPlatform().build(iter(sponsored_first))
    assert [p.price for p in products] == [1, 1, 1, 720, 740, 1080, 2160]


def test_pipeline_drops_listings_priced_as_a_range() -> None:
    """
    Test a range-priced listing is dropped rather than quoted at its floor.

    Rakuten and both Yahoo properties report a min and a max for multi-variant
    listings. Quoting the floor put a $1 single coffee cup ahead of every real product
    when the listing it came from is named for a $140 fifty-pack.
    """
    platform = RakutenPlatform()
    candidates = [
        Candidate(id="single", name="單一規格", price=120, url="https://example.test/a", price_max=120),
        Candidate(id="no-max", name="未回報上限", price=130, url="https://example.test/b"),
        Candidate(id="range", name="多規格賣場", price=1, url="https://example.test/c", price_max=140),
    ]
    assert [p.name for p in platform.build(iter(candidates))] == ["單一規格", "未回報上限"]


def test_pchome_drops_add_on_only_items() -> None:
    """Test 加價購 entries are skipped: they cannot be bought on their own."""
    platform = PChomePlatform()
    body = msgspec.json.encode(
        {
            "prods": [
                {"Id": "A", "name": "【加價購】 膠囊回收袋", "price": 1},
                {"Id": "B", "name": "濾掛咖啡 10入", "price": 199},
            ]
        }
    )
    assert [c.name for c in platform._extract([body])] == ["濾掛咖啡 10入"]


@pytest.mark.parametrize(
    "title",
    [
        "【徵】 Fiio RC-BT 藍牙耳機線",
        "藍牙耳機 維修 換電池,1~3個月",
        "深咖啡個性秋冬款襯衫一元起運費可合併",
        "愛呀！莉奈♥賣場商品滿699隨選贈一 AirPods保護套",
        "浴櫃鏡櫃皆可量身訂做1公分35元",
    ],
)
def test_yahoo_auction_drops_non_retail_listings(title: str) -> None:
    """
    Test wanted ads, services, auction bait, and gift entries never reach a caller.

    Each of these was in the cheapest ten for a real query. None is a product offered
    at the price shown, and the site exposes no field marking them.
    """
    platform = YahooAuctionPlatform()
    hit = _YahooAuctionProduct(ec_title=title, ec_buyprice=1.0, ec_item_url="https://tw.bid.yahoo.com/item/1", ec_productid="1")
    assert list(platform._extract(([hit], True))) == []


def test_yahoo_auction_keeps_ordinary_listings() -> None:
    """Test the non-retail markers do not swallow a normal product."""
    platform = YahooAuctionPlatform()
    hit = _YahooAuctionProduct(
        ec_title="SONY WF-1000XM5 真無線藍牙耳機", ec_buyprice=6990.0, ec_item_url="https://tw.bid.yahoo.com/item/2", ec_productid="2"
    )
    assert [c.name for c in platform._extract(([hit], True))] == ["SONY WF-1000XM5 真無線藍牙耳機"]
