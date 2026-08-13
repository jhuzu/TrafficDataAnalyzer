# TrafficDataAnalyzer M4 Air 測試版

此包供 Apple Silicon（M1／M2／M3／M4）Mac 測試事故資料分析與重大違規分析。資料只在本機瀏覽器與 `127.0.0.1` 間處理；事故地圖會向 OpenStreetMap 下載底圖。

## 測試前準備

1. 解壓縮 ZIP 到「下載項目」或「桌面」。
2. 確認 Mac 已有 Python 3。若雙擊啟動時顯示找不到 Python，請在 Terminal 執行 `xcode-select --install`，完成後重新開啟。
3. 第一次使用請雙擊 `安裝Python依賴.command`，完成後再雙擊啟動器。
3. 第一次雙擊 `啟動測試版.command` 若被 macOS 阻擋，請在 Finder 對檔案按右鍵，選「打開」，再選「打開」。

## 測試流程

1. 雙擊 `啟動測試版.command`；瀏覽器會開啟 `http://127.0.0.1:8765`。
2. 在「事故資料分析」上傳一份 `.xlsx` 或 `.xlsm`，確認排行、圖表、日期篩選與事故地圖。
3. 在「重大違規分析」一次選取多份 `.xlsx` 或 `.xlsm`，確認來源清單、分類統計、路段／行政區／時段排行與月季趨勢。
4. 關閉啟動時出現的 Terminal 視窗即可停止服務。

## 本測試包範圍

- 可測：Excel 讀取、事故分析、重大違規多檔分析、圖表、地圖標記、摘要、交通事故 PPTX 生成，以及 `TrafficDataAnalyzer.command` 的 Excel 匯出。
- 匯出功能使用公開 Python 套件；完成上述首次安裝後即可測試。
- `.xls` 舊格式不支援，請先在 Excel 另存為 `.xlsx` 或 `.xlsm`。

## 回報問題時請提供

- 使用的 macOS 版本與 Apple 晶片型號。
- 操作步驟、畫面截圖，以及啟動 Terminal 視窗最後 20 行訊息。
- 測試資料不要附含個資的原始檔；可改用去識別或欄位名稱範例。
