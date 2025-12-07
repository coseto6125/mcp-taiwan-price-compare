● Console 沒有顯示我的 log 輸出（可能在 reload 時被清空了）。讓我做一個總結：

  ---
  結論：可以用 Playwright 提取 Hash，但方法不同

  經過調查，從 minified JS bundle 直接提取 hash 非常困難，原因：
  1. CORS 限制無法從頁面內 fetch 外部 JS
  2. Hash 可能被混淆或分割在不同變數中

  ✅ 可行方案：攔截網路請求

  最可靠的方法是攔截 GraphQL 請求來提取 hash：

  async def extract_hash_via_playwright(platform: str) -> str | None:
      """透過攔截 GraphQL 請求來提取 hash"""
      from playwright.async_api import async_playwright

      captured_hash = None
      url = "https://tw.buy.yahoo.com/search/product?p=test" if platform == "shopping" \
            else "https://tw.bid.yahoo.com/search/auction/product?p=test"

      async with async_playwright() as p:
          browser = await p.chromium.launch()
          page = await browser.new_page()

          async def intercept(route, request):
              nonlocal captured_hash
              if "graphql.ec.yahoo.com" in request.url:
                  body = request.post_data
                  if body and "sha256Hash" in body:
                      import re
                      match = re.search(r'"sha256Hash"\s*:\s*"([a-f0-9]{64})"', body)
                      if match:
                          captured_hash = match.group(1)
              await route.continue_()

          await page.route("**/*", intercept)
          await page.goto(url, wait_until="networkidle")
          await browser.close()

      return captured_hash

  實作建議

  Fallback 策略應該是：

  1. GraphQL 失敗 (PersistedQueryNotFound)
  2. → 啟動 Playwright 攔截網路請求，獲取新 hash
  3. → 更新程式中的 hash 常數（或存入快取）
  4. → 重試 GraphQL 請求
  5. → 若仍失敗 → fallback 到 HTML parsing

  這樣可以實現「hash 自動更新」，不用手動維護。