# Price Compare MCP

台灣電商比價工具 MCP Server，支援 momo、PChome、Coupang、ETMall、Rakuten、Yahoo購物中心、Yahoo拍賣、Costco、全聯全電商、萬家福、博客來、露天市集、生活市集、松果購物 共 14 個平台的價格搜尋與比較。

**目前版本：v0.5.0** | [更新日誌](#版本歷史)

## 功能

| 工具 | 說明 |
|------|------|
| `compare_prices` | 跨平台搜尋最低價商品 |

### 參數說明

#### compare_prices

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `query` | str | (必填) | 搜尋關鍵字 |
| `top_n` | int | 20 | 回傳筆數 |
| `min_price` | int | 0 | 最低價格過濾 (0=不過濾) |
| `max_price` | int | 0 | 最高價格過濾 (0=不過濾) |
| `require_words` | list[list[str]] | None | 關鍵字分組過濾。組與組是 AND 關係，組內是 OR 關係。例：[["SONY", "索尼"], ["電視", "TV"]] = (SONY OR 索尼) AND (電視 OR TV) |
| `include_auction` | bool | False | 是否包含競標商品，影響 Yahoo 拍賣與露天市集 (預設僅含立即購買) |
| `platform` | str | None | 指定單一平台搜尋。None = 搜尋所有平台。可選：pchome, momo, coupang, etmall, rakuten, yahoo_shopping, yahoo_auction, costco, pxbox, uniprosperity, books, ruten, buy123, pcone |
| `mode` | str | "full" | 多平台搜尋的覆蓋範圍。`full` = 全部 14 個平台，約 2 秒；`fast` = 9 個次秒級平台，約 0.5 秒，略過 pcone、coupang、momo、rakuten、ruten。指定 `platform` 時此參數無效，具名平台一律查詢 |

**回傳值**：`str` (TOON 格式) - 壓縮序列化的產品列表，以降低 LLM token 消耗

### 使用範例

```python
# 搜尋所有平台最低價（預設）
compare_prices(query="SONY 50吋電視")

# 只搜尋 momo 平台
compare_prices(query="SONY 50吋電視", platform="momo")

# 只搜尋 PChome 平台的 Apple 產品
compare_prices(query="Apple AirPods Pro", platform="pchome")

# 搜尋特定品牌（符合其中一個即可）
compare_prices(
    query="無線耳機",
    require_words=[["Apple", "Beats", "Sony"]]  # 品牌過濾
)

# 複雜過濾：品牌 AND 功能
compare_prices(
    query="藍牙喇叭",
    require_words=[["JBL", "BOSE"], ["防水", "IP67"]],  # (JBL OR BOSE) AND (防水 OR IP67)
    min_price=500,
    max_price=5000
)

# 搜尋包含 Yahoo 拍賣競標商品
compare_prices(query="iPhone 15", include_auction=True)
```

> **提示**：Coupang 等平台的搜尋結果有時會包含不相關的低價商品，使用 `require_words` 可有效過濾。

> **延遲**：全平台併發的總時間等於最慢的平台。pcone 約 1.9 秒、coupang 與 momo 約 0.9 秒都是站方伺服器 render 時間，經三方獨立量測確認無法從 client 端改善（HTTP 版本、TLS 指紋、連線池、壓縮、較輕端點皆無效）。需要次秒回應時用 `mode="fast"`。

## 安裝

```bash
pip install mcp-taiwan-price-compare
# 或
uv pip install mcp-taiwan-price-compare
```

## MCP Server 配置

### Claude Desktop / Claude Code

**CLI 快速安裝（推薦）：**

```bash
claude mcp add price-compare -- uv run --directory /path/to/price_compare price-compare-mcp
```

**手動編輯配置檔：**

| 系統 | 路徑 |
|------|------|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| Linux | `~/.config/Claude/claude_desktop_config.json` |

```json
{
  "mcpServers": {
    "price-compare": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/price_compare", "price-compare-mcp"]
    }
  }
}
```

### Gemini CLI

安裝 Gemini CLI：

```bash
npm install -g @google/gemini-cli@latest
```

編輯 `~/.gemini/settings.json`：

```json
{
  "mcpServers": {
    "price-compare": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/price_compare", "price-compare-mcp"]
    }
  }
}
```

### ChatGPT（Developer Mode）

> 需要 ChatGPT Plus/Pro/Team/Enterprise 方案

ChatGPT 僅支援**遠端 HTTPS MCP server**，需先部署或使用 ngrok：

```bash
# 本地開發：使用 ngrok 建立 HTTPS 通道
ngrok http 8000
```

1. 開啟 ChatGPT → Settings → Developer mode → 啟用
2. Settings → Connectors → Create
3. 輸入 MCP server URL（ngrok 提供的 HTTPS URL）

詳細說明：[OpenAI MCP 文件](https://developers.openai.com/apps-sdk/deploy/connect-chatgpt/)

### Perplexity AI（Mac 本地）

> 目前 Perplexity 僅支援 **macOS 桌面版**的本地 MCP

1. 開啟 Perplexity Mac App → Settings → Connectors
2. 首次使用需安裝 Helper：點擊安裝 **PerplexityXPC**
3. 點擊 **Add Connector** → **Simple** 分頁
4. 填入設定：
   - **Server Name**: `price-compare`
   - **Command**: `uvx --from mcp-taiwan-price-compare price-compare-mcp`
5. 測試：輸入「幫我搜尋 iPhone 16 最低價」

詳細說明：[Perplexity MCP 文件](https://www.perplexity.ai/help-center/en/articles/11502712-local-and-remote-mcps-for-perplexity)

### 其他安裝方式

## 直接使用 (CLI)

除了作為 MCP Server，你也可以直接在終端機使用此工具進行比價：

```bash
# 安裝後可直接使用系統指令
price-compare "Nintendo Switch"
price-compare "Sony 耳機" --top 5 --min 1000 --max 5000 --desc

# 或透過 uv 執行 (如果你沒有全域安裝)
uv run price-compare "Nintendo Switch"
```

### CLI 參數說明

| 參數 | 說明 |
|------|------|
| `query` | 搜尋關鍵字 (必填) |
| `-n`, `--top` | 顯示筆數 (預設: 10) |
| `--min` | 最低價格過濾 |
| `--max` | 最高價格過濾 |
| `--desc` | 價格由高到低排序 (預設為低到高) |

---

**使用 uvx（無需安裝）：**

```json
{
  "mcpServers": {
    "price-compare": {
      "command": "uvx",
      "args": ["--from", "mcp-taiwan-price-compare", "price-compare-mcp"]
    }
  }
}
```

**使用 npx + stdio wrapper：**

```json
{
  "mcpServers": {
    "price-compare": {
      "command": "npx",
      "args": ["-y", "@anthropic-ai/mcp-proxy", "--", "uv", "run", "price-compare-mcp"]
    }
  }
}
```

## CLI 使用

```bash
# 搜尋最便宜的 10 筆
uv run python -m price_compare "iPhone 15"

# 指定數量與價格範圍
uv run python -m price_compare "藍牙耳機" -n 20 --min 500 --max 3000

# 價格由高到低
uv run python -m price_compare "機械鍵盤" --desc
```

## 參考資料

- [Model Context Protocol 官方文件](https://modelcontextprotocol.io/docs/develop/connect-local-servers)
- [Claude Desktop MCP 設定指南](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop)
- [Desktop Extensions 一鍵安裝](https://www.anthropic.com/engineering/desktop-extensions)

## 版本歷史

### v0.5.0 (2026-08-01)
- 🏗️ **架構深化**：`BasePlatform` 由純介面宣告改為承載共用管線（去重、價格轉型、價格上下界、關鍵字分組、排序、截斷）。各平台只需實作 `_fetch`（連網）與 `_extract`（純函式），規則無法在平台間漂移
- 🐛 **ETMall 靜默失效**：`PageSize` 超過約 45 會回 400，而 service 固定傳 100，等於該平台在每次全平台搜尋都回 0 筆。改為分頁抓取後恢復
- 🐛 **排序宣稱不可信**：Coupang 的 `salePriceAsc`（實測 16 處逆序）與 Rakuten 的 `LowestPrice`（前 5 筆為贊助排序 720/2160/740/1080/1160）都不是真正升冪。改為一律由管線排序，`ordered_by_price` 這個會出錯的宣告直接移除
- 🧹 **依平台的基礎過濾**：各站以自身的資料特性排除「不是該商品售價」的刊登
  - Rakuten／Yahoo拍賣：站方回報價格區間者為多規格賣場的地板價（Rakuten 咖啡查詢中 47/100 是多規格，一個 $1~$140 的咖啡紙杯賣場會以 $1 排在最前）。實測 206 筆區間刊登的價差分佈在 6 倍與 10 倍之間有明顯谷底，超過 8 倍者排除。Yahoo購物中心沒有回報區間的欄位，不適用此規則
  - PChome：`【加價購】` 無法單獨購買
  - Yahoo拍賣：【徵】／求購／收購中（買方刊登）、請勿下標等佔位刊登、訂金專區、一元起標、滿額贈。比對的是交易意圖用語而非主題字，因此「維修工具」「訂製印章」這類以用途命名的正常商品會保留（早期版本比對裸的維修／訂製／客製化，60 筆結果丟掉 49 筆）
  - 仍會保留的是關鍵字灌水造成的偶然命中（例如 $1 髮圈因有「咖啡色」選項而命中「咖啡」），那屬相關性問題，請用 `require_words` 過濾
- 🐛 **ETMall 與 PChome 缺少去重**：其餘 12 個平台都有，這兩個沒有，共用管線一併補上
- 🛒 **平台擴充**：7 → 14 個平台，新增 Costco、全聯全電商、萬家福、博客來、露天市集、生活市集、松果購物，各附完整整合測試
- 🐛 **Coupang 修復**：該站改版為 Next.js 後舊選擇器全數失效、靜默回傳 0 筆。改以 CSS Module 前綴比對，並將已失效的 `sorter=LOWEST_PRICE_ASC` 換成 `salePriceAsc` 恢復低價優先
- ⚡ **`mode` 參數**：`full`（預設，14 平台，約 2.1 秒）／`fast`（9 個次秒級平台，約 0.5 秒）。指定 `platform` 時不受影響，慢平台一律可查
- 🔬 **離線解析測試**：新增 `tests/fixtures/` 與 `tests/test_parsers.py`，解析回歸不再需要真實網路才驗得出來（70 個測試、約 1.2 秒）。另附 `tests/fixtures/regenerate.py` 一次重抓全部 17 個 fixture，寫入前先用測試同一套 parser 讀回來，解析結果比現有 fixture 差就拒寫
- 🔧 **CI 修復**：移除無 cp313 wheel 的 `regex-rs`（改用 stdlib `re`，實測快 2.4 倍）、修正 mypy 錯誤、平台矩陣補齊至 14 個
- 🚀 **效能**：pcone 改用持久連線（2.42 → 2.00 秒）、rakuten 修正結果數上限（原本寫死只回 60 筆）、service 層加上單平台 3 秒上限

### v0.4.0 (2026-05-13)
- 📦 **CLI 全域指令**：新增 `price-compare` 與 `price-compare-mcp` 進入點
- ⬆️ **依賴升級**

### v0.3.3 (2025-12-08)
- 🔄 **工具統一**：合併 `compare_prices` 和 `search_platform` 為單一工具
  - `platform=None`（預設）：搜尋所有 14 平台
  - `platform="momo"` 等：搜尋指定單一平台
- 📝 **Prompt 強化**：優化 MCP 工具描述，讓 LLM 更容易理解使用方式

### v0.3.2 (2025-12-08)
- 🚀 **搜尋優化**：動態調整搜尋量，根據 `require_words` 過濾條件自動增加搜尋範圍
- 🎯 **結果完整性**：確保過濾品牌/型號時不漏掉最低價商品
- 📝 **Prompt 強化**：改進工具描述，明確標示 ✅ 正確用法和 ❌ 錯誤用法

### v0.3.1 (2025-12-08)
- 🐛 **Bug 修復**：修正 Yahoo 拍賣價格解析問題
- 📝 **文件更新**：完善 README 和 API 文件

### v0.3.0 (2025-12-08)
- ✨ **重大重構**：大規模架構重構，優化平台搜尋效率
- 🔄 **參數優化**：
  - 重命名 `coupang_keywords` → `require_words`（支援多平台）
  - 新增關鍵字分組邏輯（組間 AND、組內 OR）
  - 新增 `include_auction` 參數支援 Yahoo 拍賣競標商品
- 🚀 **性能改進**：
  - 使用 TOON 格式壓縮回應，降低 LLM token 消耗 ~30%
  - 優化平台架構，改進並發搜尋效率
- 🧪 **完整測試**：新增 CI/CD pipeline 和全平台測試覆蓋
- 📦 **依賴更新**：新增 `toon_format` 用於結果序列化

### v0.2.1 (2025-12-07)
- ✨ 更新 momo 和 rakuten 平台的 GraphQL 實現
- 📝 新增 yahoo 購物中心規劃文檔
- 🔧 優化 coupang 平台實現

### v0.2.0
- 新增多個電商平台支持
- 初版功能完善

### v0.1.0
- 項目初始版本
