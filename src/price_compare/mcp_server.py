"""MCP server for price comparison across multiple Taiwan e-commerce platforms."""

from fastmcp import FastMCP

from price_compare.service import PriceCompareService

mcp = FastMCP(name="price-compare")
service = PriceCompareService()


@mcp.tool()
async def compare_prices(
    query: str,
    top_n: int = 20,
    min_price: int = 0,
    max_price: int = 0,
    coupang_keywords: list[str] | None = None,
) -> list[dict]:
    """
    Search for the cheapest products across Coupang, momo, PChome, ETMall, Rakuten, Yahoo購物中心, and Yahoo拍賣.

    Args:
        query: Product search keyword (e.g., "iPhone 15", "藍牙耳機")
        top_n: Number of results to return (default: 20)
        min_price: Minimum price filter, use to exclude accessories (default: 0 = no filter)
        max_price: Maximum price filter (default: 0 = no filter)
        coupang_keywords: Required keywords for Coupang results - product name must contain ALL
            these keywords (case-insensitive). Use for brand/model filtering. (default: None)

    Returns:
        List of products with name, price, url, and platform
    """
    products = await service.get_cheapest(
        query, top_n, min_price=min_price, max_price=max_price, coupang_keywords=coupang_keywords
    )
    return [p.to_dict() for p in products]


@mcp.tool()
async def search_pchome(query: str, max_results: int = 20) -> list[dict]:
    """
    Search products on PChome 24h only.

    Args:
        query: Product search keyword
        max_results: Maximum number of results (default: 20)

    Returns:
        List of products sorted by price (low to high)
    """
    products = await service.search_pchome(query, max_results)
    return [p.to_dict() for p in products]


@mcp.tool()
async def search_momo(query: str, max_results: int = 20) -> list[dict]:
    """
    Search products on momo shopping only.

    Args:
        query: Product search keyword
        max_results: Maximum number of results (default: 20)

    Returns:
        List of products sorted by price (low to high)
    """
    products = await service.search_momo(query, max_results)
    return [p.to_dict() for p in products]


@mcp.tool()
async def search_coupang(
    query: str,
    max_results: int = 20,
    required_keywords: list[str] | None = None,
) -> list[dict]:
    """
    Search products on Coupang Taiwan only.

    Args:
        query: Product search keyword
        max_results: Maximum number of results (default: 20)
        required_keywords: Product name must contain ALL these keywords (case-insensitive).
            Use for brand/model filtering. (default: None)

    Returns:
        List of products sorted by price (low to high)
    """
    products = await service.search_coupang(query, max_results, required_keywords)
    return [p.to_dict() for p in products]


@mcp.tool()
async def search_etmall(query: str, max_results: int = 20) -> list[dict]:
    """
    Search products on ETMall (東森購物) only.

    Args:
        query: Product search keyword
        max_results: Maximum number of results (default: 20)

    Returns:
        List of products sorted by price (low to high)
    """
    products = await service.search_etmall(query, max_results)
    return [p.to_dict() for p in products]


@mcp.tool()
async def search_rakuten(
    query: str,
    max_results: int = 20,
    required_keywords: list[str] | None = None,
) -> list[dict]:
    """
    Search products on Rakuten Taiwan (樂天市場) only.

    Args:
        query: Product search keyword
        max_results: Maximum number of results (default: 20)
        required_keywords: Product name must contain ALL these keywords (case-insensitive).
            Use for brand/model filtering. (default: None)

    Returns:
        List of products sorted by price (low to high)
    """
    products = await service.search_rakuten(query, max_results, required_keywords)
    return [p.to_dict() for p in products]


@mcp.tool()
async def search_yahoo_shopping(query: str, max_results: int = 20) -> list[dict]:
    """
    Search products on Yahoo Shopping (Yahoo購物中心) only.

    Args:
        query: Product search keyword
        max_results: Maximum number of results (default: 20)

    Returns:
        List of products sorted by price (low to high)
    """
    products = await service.search_yahoo_shopping(query, max_results)
    return [p.to_dict() for p in products]


@mcp.tool()
async def search_yahoo_auction(query: str, max_results: int = 20) -> list[dict]:
    """
    Search products on Yahoo Auction (Yahoo拍賣) only.

    Args:
        query: Product search keyword
        max_results: Maximum number of results (default: 20)

    Returns:
        List of products sorted by price (low to high)
    """
    products = await service.search_yahoo_auction(query, max_results)
    return [p.to_dict() for p in products]


def main() -> None:
    """Entry point for MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
