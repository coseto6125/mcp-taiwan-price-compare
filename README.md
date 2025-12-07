# Price Compare MCP

台灣電商比價工具 MCP Server，支援 momo、PChome、Coupang、ETMall、Rakuten、Yahoo購物中心、Yahoo拍賣 價格搜尋與比較。

**目前版本：v0.3.2** | [更新日誌](#版本歷史)

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
| `include_keywords` | list[list[str]] | None | 關鍵字分組過濾。組與組是 AND 關係，組內是 OR 關係。例：[["SONY", "索尼"], ["電視", "TV"]] = (SONY OR 索尼) AND (電視 OR TV) |
| `include_auction` | bool | False | 是否包含 Yahoo 拍賣競標商品 (預設僅含立即購買) |

**回傳值**：`str` (TOON 格式) - 壓縮序列化的產品列表，以降低 LLM token 消耗

### 使用範例

```python
# 搜尋 SONY 電視，過濾不相關結果
compare_prices(
    query="SONY 50吋電視",
    include_keywords=[["SONY"]]  # 結果必須包含 "SONY"
)

# 搜尋特定品牌（符合其中一個即可）
compare_prices(
    query="無線耳機",
    include_keywords=[["Apple", "Beats", "Sony"]]  # 品牌過濾
)

# 複雜過濾：品牌 AND 功能
compare_prices(
    query="藍牙喇叭",
    include_keywords=[["JBL", "BOSE"], ["防水", "IP67"]],  # (JBL OR BOSE) AND (防水 OR IP67)
    min_price=500,
    max_price=5000
)

# 搜尋包含 Yahoo 拍賣競標商品
compare_prices(
    query="iPhone 15",
    include_auction=True
)
```

> **提示**：Coupang 等平台的搜尋結果有時會包含不相關的低價商品，使用 `include_keywords` 可有效過濾。

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

### 其他安裝方式

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

### v0.3.2 (2025-12-08)
- 🚀 **搜尋優化**：動態調整搜尋量，根據 `require_words` 過濾條件自動增加搜尋範圍
- 🎯 **結果完整性**：確保過濾品牌/型號時不漏掉最低價商品
- 🔧 **程式碼優化**：新增 `calc_search_multiplier()` 工具函數，pchome 新增 `_PAGE_SIZE` 常量

### v0.3.1 (2025-12-08)
- 🐛 **Bug 修復**：修正 Yahoo 拍賣價格解析問題
- 📝 **文件更新**：完善 README 和 API 文件

### v0.3.0 (2025-12-08)
- ✨ **重大重構**：統一 MCP 工具，只保留 `compare_prices` 通用工具
- 🔄 **參數優化**：
  - 重命名 `coupang_keywords` → `include_keywords`（支援多平台）
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
