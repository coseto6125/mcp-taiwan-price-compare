# 解析測試用的固定回應

`tests/test_parsers.py` 用這裡的檔案離線驅動各平台的解析器。其餘測試都得發真實請求，
站台掛掉和解析器壞掉會是同一種紅燈；這些不會，它們只在解析本身壞掉時失敗。

每個檔案是該站搜尋「咖啡」的真實回應，裁掉頁面其餘部分只留前幾個商品區塊。裁切是為了
能進版控（Coupang 原始頁面 1.17MB，其中 71% 是 RSC flight payload），解析器看到的
標記結構與線上完全相同。

| 檔案 | 平台 | 商品數 |
|-----------------------------|---------------|-------|
| `coupang_search.html` | coupang | 6 |
| `books_search.html` | books | 6 |
| `uniprosperity_search.html` | uniprosperity | 8 |

## 什麼時候該重抓

站台改版、你更新了解析器，**而且**已經確認線上真的變了 — 這時重抓。fixture 的 diff
就是那次改版的紀錄。

解析測試紅了但線上沒變，那是真的回歸，改解析器而不是改 fixture。

## 怎麼重抓

```bash
.venv/bin/python - <<'PY'
import asyncio, pathlib
from urllib.parse import quote
import never_primp as primp

OUT = pathlib.Path("tests/fixtures")
SOURCES = [
    ("coupang_search.html",
     "https://www.tw.coupang.com/np/search?q={q}&sorter=salePriceAsc&listSize=60",
     '<li class="ProductUnit_productUnit__', 6),
    ("books_search.html",
     "https://search.books.com.tw/search/query/cat/all/sort/8/key/{q}",
     '<div class="table-td" id="prod-itemlist-', 6),
    ("uniprosperity_search.html",
     "https://online.uni-prosperity.com.tw/on/demandware.store/"
     "Sites-Uniprosperity-Site/default/Search-UpdateGrid?q=q%3D{q}",
     '<a class="gtm-product-alink"', 8),
]

async def main():
    q = quote("咖啡")
    async with primp.AsyncClient(impersonate="chrome_142", impersonate_os="windows",
                                 timeout=30.0, follow_redirects=True) as c:
        for name, url, delimiter, keep in SOURCES:
            body = (await c.get(url.format(q=q))).text
            parts = body.split(delimiter)
            trimmed = parts[0][-2000:] + delimiter + delimiter.join(parts[1 : keep + 1])
            (OUT / name).write_text(trimmed, encoding="utf-8")
            print(f"{name}: {len(parts) - 1} 個區塊，保留 {keep}")

asyncio.run(main())
PY
```

保留的商品數若有變動，同步更新 `tests/test_parsers.py` 的 `PARSERS` 表。

博客來對密集請求會直接 reset 連線，重抓失敗的話隔幾分鐘再試。
