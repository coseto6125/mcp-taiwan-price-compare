"""CLI entry point for price comparison."""

import argparse
import asyncio

from price_compare.service import PriceCompareService

# ANSI Color Codes
COLORS = {
    "momo": "\033[38;5;206m",  # Pink
    "pchome": "\033[38;5;196m",  # Red
    "coupang": "\033[38;5;40m",  # Green
    "etmall": "\033[38;5;214m",  # Orange
    "rakuten": "\033[38;5;160m",  # Dark Red
    "yahoo_shopping": "\033[38;5;93m",  # Purple
    "yahoo_auction": "\033[38;5;129m",  # Light Purple
    "default_plat": "\033[38;5;250m",  # Gray
    "reset": "\033[0m",
    "bold": "\033[1m",
    "price": "\033[38;5;51m",  # Cyan
    "url": "\033[38;5;244m",  # Gray
    "header": "\033[1;38;5;226m",  # Bold Yellow
}


def get_platform_color(platform: str) -> str:
    """Get color code for platform."""
    return COLORS.get(platform, COLORS["default_plat"])


def format_price(price: int) -> str:
    """Format price with thousand separators."""
    return f"${price:,}"


async def run(
    query: str,
    top_n: int = 10,
    min_price: int = 0,
    max_price: int = 0,
    descending: bool = False,
) -> None:
    """Run price comparison and display results."""
    print(f"\n{COLORS['bold']}搜尋商品:{COLORS['reset']} {COLORS['header']}{query}{COLORS['reset']}")

    if min_price > 0 or max_price > 0:
        price_range = []
        if min_price > 0:
            price_range.append(f"最低 {COLORS['price']}${min_price:,}{COLORS['reset']}")
        if max_price > 0:
            price_range.append(f"最高 {COLORS['price']}${max_price:,}{COLORS['reset']}")
        print(f"價格範圍: {' ~ '.join(price_range)}")

    if descending:
        print("排序: 高→低")

    print(f"{COLORS['url']}={'=' * 60}{COLORS['reset']}")

    service = PriceCompareService()
    products = await service.get_cheapest(query, top_n, min_price=min_price, max_price=max_price, descending=descending)

    if not products:
        print(f"{COLORS['bold']}找不到任何商品{COLORS['reset']}")
        return

    print(f"\n找到 {COLORS['header']}{len(products)}{COLORS['reset']} 筆商品:\n")

    for i, product in enumerate(products, 1):
        plat_color = get_platform_color(product.platform)
        plat_tag = f"[{plat_color}{product.platform:7}{COLORS['reset']}]"
        price_tag = f"{COLORS['price']}{format_price(product.price):>10}{COLORS['reset']}"
        name = f"{product.name[:50]}{'...' if len(product.name) > 50 else ''}"

        print(f"{i:2}. {plat_tag} {price_tag}")
        print(f"    {COLORS['bold']}商品:{COLORS['reset']} {name}")
        print(f"    {COLORS['bold']}網址:{COLORS['reset']} {COLORS['url']}{product.url}{COLORS['reset']}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="比價工具 - 支援全台大電商平台最低價搜尋 (momo, PChome, Coupang, Yahoo等)")
    parser.add_argument("query", help="搜尋關鍵字")
    parser.add_argument("-n", "--top", type=int, default=10, help="顯示筆數 (預設: 10)")
    parser.add_argument("--min", type=int, default=0, help="最低價格過濾")
    parser.add_argument("--max", type=int, default=0, help="最高價格過濾")
    parser.add_argument("--desc", action="store_true", help="價格由高到低排序")

    args = parser.parse_args()
    asyncio.run(run(args.query, args.top, args.min, args.max, args.desc))


if __name__ == "__main__":
    main()
