"""CLI entry point for price comparison."""

import argparse
import asyncio

from price_compare.service import PriceCompareService


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
    print(f"\n搜尋商品: {query}")
    if min_price > 0 or max_price > 0:
        price_range = []
        if min_price > 0:
            price_range.append(f"最低 ${min_price:,}")
        if max_price > 0:
            price_range.append(f"最高 ${max_price:,}")
        print(f"價格範圍: {' ~ '.join(price_range)}")
    if descending:
        print("排序: 高→低")
    print("=" * 60)

    service = PriceCompareService()
    products = await service.get_cheapest(query, top_n, min_price=min_price, max_price=max_price, descending=descending)

    if not products:
        print("找不到任何商品")
        return

    print(f"\n找到 {len(products)} 筆商品:\n")

    for i, product in enumerate(products, 1):
        print(f"{i:2}. [{product.platform:7}] {format_price(product.price):>10}")
        print(f"    商品: {product.name[:50]}{'...' if len(product.name) > 50 else ''}")
        print(f"    網址: {product.url}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="比價工具 - 搜尋 momo 與 PChome 最低價商品")
    parser.add_argument("query", help="搜尋關鍵字")
    parser.add_argument("-n", "--top", type=int, default=10, help="顯示筆數 (預設: 10)")
    parser.add_argument("--min", type=int, default=0, help="最低價格過濾")
    parser.add_argument("--max", type=int, default=0, help="最高價格過濾")
    parser.add_argument("--desc", action="store_true", help="價格由高到低排序")

    args = parser.parse_args()
    asyncio.run(run(args.query, args.top, args.min, args.max, args.desc))


if __name__ == "__main__":
    main()
