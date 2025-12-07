# v0.3.3 技術細節更動

**發布日期：2025-12-08**
**上一版本：v0.3.2**
**主題：統一 MCP 工具**

## 概述

v0.3.3 將 `compare_prices` 和 `search_platform` 合併為單一工具，簡化 LLM 調用邏輯。

## 核心變更

### 1. 統一 MCP 工具

**修改前**（v0.3.2）：
```python
# 搜尋所有平台
compare_prices(query="SONY 電視")

# 搜尋單一平台（需要用另一個工具）
search_platform(query="SONY 電視", platform="momo")
```

**修改後**（v0.3.3）：
```python
# 搜尋所有平台（預設）
compare_prices(query="SONY 電視")

# 搜尋單一平台（同一工具，加 platform 參數）
compare_prices(query="SONY 電視", platform="momo")
```

### 2. Prompt 強化

優化 MCP 工具描述，讓 LLM 更容易理解：

```python
"""
Search cheapest products across all platforms (or single platform if specified).

Platforms: Coupang, momo, PChome, ETMall, Rakuten, Yahoo Shopping, Yahoo Auction

Args:
    query: Complete product description (brand + type + specs).
        ✅ "SONY 50吋電視", "Apple AirPods Pro"
        ❌ "電視", "耳機" (too broad, returns accessories)

    platform: Search single platform only.
        None = search ALL platforms (default)
        Options: pchome, momo, coupang, etmall, rakuten, yahoo_shopping, yahoo_auction
"""
```

## 檔案變更

```
src/price_compare/mcp_server.py   # 合併工具，刪除 search_platform
pyproject.toml                    # 版本號 0.3.2 → 0.3.3
README.md                         # 更新範例和版本歷史
docs/CHANGELOG_v0.3.3.md          # 新增本檔案
```

## API 變更

| 項目 | v0.3.2 | v0.3.3 |
|------|--------|--------|
| 工具數量 | 2 個 | 1 個 |
| `compare_prices` | 只搜全部平台 | 支援 `platform` 參數 |
| `search_platform` | 搜單一平台 | 已移除 |

## 向後相容性

- `compare_prices` 保持相容，原有呼叫方式不受影響
- `search_platform` 已移除，需改用 `compare_prices(platform="xxx")`

---

**版本控制**：Git tag `v0.3.3`
**發布日期**：2025-12-08
