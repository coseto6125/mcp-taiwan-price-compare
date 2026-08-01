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

## `*_payload.json` — 其餘 11 個平台

HTML 以外的平台，`_fetch` 回傳的是解碼後的結構而非原始位元組，形狀各站不同
（`list[dict]`、`list[Struct]`、`list[bytes]`、`tuple[hits, buy_now_only]`）。這些檔案存的是
該結構序列化後的 JSON，`tests/test_parsers.py` 的 `PAYLOAD_LOADERS` 負責載回原形。

`tests/test_parsers.py` 的 `EXPECTED` 表釘住每個 fixture 應解析出幾筆、通過管線後剩幾筆。
改動 fixture 就要同步更新該表 — 那個表是「parser 沒死掉但退化成只回一筆」這類問題唯一
抓得到的地方。

Costco 的 fixture 刻意混入 2 筆無標價的賣場現場品項，用來驗證管線會丟棄它們；重抓後
若這個比例變了，`EXPECTED["costco"]` 要跟著改。

重抓執行 `tests/fixtures/regenerate.py`：

```bash
.venv/bin/python tests/fixtures/regenerate.py
```

該腳本會重抓全部 14 個 fixture（3 個 HTML 加 11 個 JSON payload）並印出各自的解析筆數，
把印出的數字對回 `EXPECTED`。

## 什麼時候該重抓

站台改版、你更新了解析器，**而且**已經確認線上真的變了 — 這時重抓。fixture 的 diff
就是那次改版的紀錄。

解析測試紅了但線上沒變，那是真的回歸，改解析器而不是改 fixture。


