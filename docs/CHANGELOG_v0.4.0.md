# Changelog

## v0.4.0 (2026-05-14)

### 🚀 Features (新增功能)
- **CLI 體驗大升級**
  - 獨立命令列工具：現在支援安裝後直接在系統終端機呼叫 `price-compare` 指令。
  - 豐富的彩色輸出：使用 ANSI color codes 為各大電商平台設計了專屬的顏色標籤。
  - 重點資訊高亮：搜尋目標與價格均提供色彩高亮，增強可讀性。
  - 在 `README.md` 中新增完整的 CLI 指令使用教學。

### ⚡ Performance (效能提升)
- **序列化核心替換**
  - 將結果編碼引擎從 `toon_format` 替換為效能更高的 `etoon` (v0.4.1)，並優化資料結構處理。
- **記憶體優化**
  - 使用 generator expressions 取代中介清單 (List Comprehension)，降低記憶體消耗。
  - `_flatten` 操作改採 `itertools.chain.from_iterable` 作為高效率備選方案。

### 🐛 Bug Fixes (問題修復)
- **測試環境相容性**
  - 修復在無介面環境執行測試時因缺少 `tkinter` 導致的 `ModuleNotFoundError` 錯誤，並加入容錯回退機制。
- **斷言穩定度強化**
  - 修正平台過濾測試中使用過於廣泛之關鍵字造成的誤判問題，改用明確商品標的 (Nintendo Switch OLED) 以確保搜尋斷言一致。
- 移除舊版廢棄工具 `search_platform` 的相關遺留測試碼，消彌潛在語法錯誤風險。

### 🧹 Refactoring (程式碼重構)
- 抽離共用常式至 `utils.py`，保持 `service.py` 的精簡。
- 執行 `ruff check --fix` 和 `ruff format`，確保整個專案的排版格式符合規範。
