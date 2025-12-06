# Price Compare MCP

台灣電商比價工具 MCP Server，支援 momo、PChome、Coupang 價格搜尋與比較。

## 功能

- `compare_prices` - 跨平台搜尋最低價商品
- `search_pchome` - 搜尋 PChome 24h
- `search_momo` - 搜尋 momo 購物
- `search_coupang` - 搜尋 Coupang 台灣

## 安裝

```bash
uv pip install -e .
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
      "args": ["--from", "git+https://github.com/your-repo/price-compare", "price-compare-mcp"]
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
