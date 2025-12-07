"""MCP server for price comparison across Taiwan e-commerce platforms."""

from typing import Literal

from fastmcp import FastMCP
from msgspec import structs
from toon_format import encode as toon_encode

from price_compare.models import Product
from price_compare.service import PriceCompareService


def _to_toon(products: list[Product]) -> str:
    """Convert products to TOON format for LLM token efficiency."""
    return toon_encode([structs.asdict(p) for p in products])


mcp = FastMCP(name="price-compare")
service = PriceCompareService()

# Valid platform names
PlatformName = Literal["pchome", "momo", "coupang", "etmall", "rakuten", "yahoo_shopping", "yahoo_auction"]


@mcp.tool()
async def compare_prices(
    query: str,
    top_n: int = 20,
    min_price: int = 0,
    max_price: int = 0,
    include_keywords: list[list[str]] | None = None,
    include_auction: bool = False,
) -> str:
    """
    Search cheapest products across all platforms: Coupang, momo, PChome, ETMall, Rakuten, Yahoo Shopping, Yahoo Auction.

    Args:
        query: Search keyword (e.g., "iPhone 15", "藍牙耳機")
        top_n: Results count (default: 20)
        min_price: Min price filter, 0=off (default: 0)
        max_price: Max price filter, 0=off (default: 0)
        include_keywords: Keyword groups filter. Groups are AND, within group is OR.
            e.g. [["SONY", "索尼"], ["電視", "TV"]] = (SONY OR 索尼) AND (電視 OR TV)
        include_auction: Include Yahoo auction bids (default: False, buy-now only)

    Returns:
        TOON format: name, price, url, platform
    """
    products = await service.get_cheapest(
        query,
        top_n,
        min_price=min_price,
        max_price=max_price,
        include_keywords=include_keywords,
        include_auction=include_auction,
    )
    return _to_toon(products)


@mcp.tool()
async def search_platform(
    query: str,
    platform: PlatformName,
    max_results: int = 20,
    min_price: int = 0,
    max_price: int = 0,
    include_keywords: list[list[str]] | None = None,
    include_auction: bool = False,
) -> str:
    """
    Search single platform only.

    Args:
        query: Search keyword
        platform: One of: pchome, momo, coupang, etmall, rakuten, yahoo_shopping, yahoo_auction
        max_results: Results count (default: 20)
        min_price: Min price filter, 0=off (default: 0)
        max_price: Max price filter, 0=off (default: 0)
        include_keywords: Keyword groups filter (see compare_prices)
        include_auction: Yahoo auction only - include bids (default: False)

    Returns:
        TOON format sorted by price (low to high)
    """
    products = await service.platforms[platform].search(
        query,
        max_results,
        min_price,
        max_price,
        include_keywords,
        include_auction=include_auction,
    )
    return _to_toon(products)


def main() -> None:
    """Entry point for MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
