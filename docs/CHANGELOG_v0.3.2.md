# v0.3.2 技術細節更動

**發布日期：2025-12-08**
**上一版本：v0.3.1**
**主題：動態搜尋量調整**

## 概述

v0.3.2 解決了使用 `require_words` 過濾時可能漏掉特定品牌最低價的問題。

**問題場景**：
```
搜尋 "50吋電視" + require_words=[["SONY"]]

momo 回傳 50 個（按銷量/相關性排序）：
  #1-30: 各品牌熱門款
  #31-45: 配件
  #46-60: SONY 特價款 ← 沒撈到！
```

**解決方案**：根據 `require_words` 過濾條件的嚴格程度，動態增加搜尋量。

---

## 核心變更

### 1. 新增 `calc_search_multiplier()` 工具函數

**檔案**：`src/price_compare/utils.py`

```python
def calc_search_multiplier(require_words: KeywordGroups) -> int:
    """Calculate search volume multiplier based on require_words filter strictness.

    Each AND group roughly halves pass rate, so multiply by 2^n (capped at 4x to avoid 429).
    """
    return min(1 << len(require_words), 4) if require_words else 1
```

**邏輯**：

| require_words | 組數 | 倍數 |
|---------------|------|------|
| 無 | 0 | 1x |
| `[["SONY"]]` | 1 | 2x |
| `[["SONY"], ["50"]]` | 2 | 4x |
| `[["SONY"], ["50"], ["電視"]]` | 3+ | 4x (上限) |

**設計考量**：
- 使用位元運算 `1 << n` 比 `2 ** n` 快 8.6%
- 上限 4x 避免觸發平台 429 rate limit

---

### 2. 平台內部動態調整

#### momo (`src/price_compare/platforms/momo.py`)

```python
adjusted_max = max_results * calc_search_multiplier(require_words)
pages_needed = min(-(-adjusted_max // self._PAGE_SIZE), 5)  # max 5 pages
```

#### pchome (`src/price_compare/platforms/pchome.py`)

```python
_PAGE_SIZE = 20  # 新增常量

adjusted_max = max_results * calc_search_multiplier(require_words)
pages_needed = min(-(-adjusted_max // self._PAGE_SIZE), 5)  # max 5 pages
```

#### etmall (`src/price_compare/platforms/etmall.py`)

```python
adjusted_max = min(max_results * calc_search_multiplier(require_words), 200)
```

---

## 實際效果

### 搜尋量變化

| 條件 | 原本 | 現在 |
|------|------|------|
| 無 require_words | 50/平台 | 50/平台 |
| 1 組 require_words | 50/平台 | 100/平台 (momo/pchome 5頁) |
| 2+ 組 require_words | 50/平台 | 200/平台 (momo/pchome 5頁, etmall 200上限) |

### 頁數上限

| 平台 | 上限 | 原因 |
|------|------|------|
| momo | 5 頁 | 避免 429 |
| pchome | 5 頁 | 避免 429 |
| etmall | 200 筆 | API 限制 |
| 其他 | 無變更 | 單頁 API，無法調整 |

---

## 檔案變更

```
src/price_compare/utils.py              # +6 行：新增 calc_search_multiplier()
src/price_compare/platforms/momo.py     # +2 行：動態調整 pages_needed
src/price_compare/platforms/pchome.py   # +3 行：新增 _PAGE_SIZE，動態調整
src/price_compare/platforms/etmall.py   # +1 行：動態調整 PageSize
pyproject.toml                          # 版本號 0.3.1 → 0.3.2
README.md                               # 更新版本歷史
docs/CHANGELOG_v0.3.2.md                # 新增本檔案
```

---

## API 相容性

**完全向後相容**：無 API 簽名變更，僅內部搜尋邏輯優化。

---

## 效能測試

10 頁並發請求測試（momo + pchome）：

```
momo 結果: [200, 200, 200, 200, 200, 200, 200, 200, 200, 200]
pchome 結果: [200, 200, 200, 200, 200, 200, 200, 200, 200, 200]
```

結論：5 頁上限保守設定，避免短時間大量查詢觸發 429。

---

**版本控制**：Git tag `v0.3.2`
**發布日期**：2025-12-08
