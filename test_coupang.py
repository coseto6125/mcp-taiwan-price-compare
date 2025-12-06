import asyncio

from price_compare.platforms.coupang import CoupangPlatform


async def test():
    platform = CoupangPlatform()
    try:
        results = await platform.search("Iphone 17", max_results=5)
        print(f"找到 {len(results)} 個結果")
        for p in results[:3]:
            print(f"  - {p.name[:30]}... ${p.price}")
    except Exception as e:
        print(f"錯誤: {e}")
    finally:
        await platform.close()


asyncio.run(test())
