# Price Compare MCP

台灣電商比價工具 MCP Server，支援 momo、PChome、Coupang、ETMall、Rakuten、Yahoo購物中心、Yahoo拍賣 價格搜尋與比較。

**目前版本：v0.2.1** | [更新日誌](#版本歷史)

## 功能

| 工具 | 說明 |
|------|------|
| `compare_prices` | 跨平台搜尋最低價商品 |
| `search_pchome` | 搜尋 PChome 24h |
| `search_momo` | 搜尋 momo 購物 |
| `search_coupang` | 搜尋 Coupang 台灣 |
| `search_etmall` | 搜尋 ETMall 東森購物 |
| `search_rakuten` | 搜尋 Rakuten 樂天市場 |
| `search_yahoo_shopping` | 搜尋 Yahoo 購物中心 |
| `search_yahoo_auction` | 搜尋 Yahoo 拍賣 |

### 參數說明

#### compare_prices

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `query` | str | (必填) | 搜尋關鍵字 |
| `top_n` | int | 20 | 回傳筆數 |
| `min_price` | int | 0 | 最低價格過濾 (0=不過濾) |
| `max_price` | int | 0 | 最高價格過濾 (0=不過濾) |
| `coupang_keywords` | list[str] | None | Coupang 必要關鍵字過濾 (不分大小寫) |

#### search_coupang

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `query` | str | (必填) | 搜尋關鍵字 |
| `max_results` | int | 20 | 回傳筆數 |
| `required_keywords` | list[str] | None | 必要關鍵字過濾，產品名稱須包含所有關鍵字 (不分大小寫) |

### 使用範例

```python
# 搜尋 SONY 電視，過濾 Coupang 不相關結果
compare_prices(
    query="SONY 50吋電視",
    coupang_keywords=["SONY"]  # Coupang 結果必須包含 "SONY"
)

# 搜尋特定品牌+型號
search_coupang(
    query="iPhone 15 Pro",
    required_keywords=["iPhone", "15", "Pro"]  # 必須同時包含這三個關鍵字
)
```

> **提示**：Coupang 的搜尋結果有時會包含不相關的低價商品，使用 `coupang_keywords` 可有效過濾。

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

### v0.2.1 (2025-12-07)
- ✨ 更新 momo 和 rakuten 平台的 GraphQL 實現
- 📝 新增 yahoo 購物中心規劃文檔
- 🔧 優化 coupang 平台實現

### v0.2.0
- 新增多個電商平台支持
- 初版功能完善

### v0.1.0
- 項目初始版本
