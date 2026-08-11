# TrafficDataAnalyzer 待辦

## 架構重構

- [x] 抽出 `core/excel/` 資料讀取入口與統一資料契約。
- [x] 支援一般 `.xlsx/.xlsm` 工作表，並與 Pivot Cache 自動比較。
- [x] 建立事故專屬 `data/transformer.py` 與不可變 `AccidentDataset`。
- [x] 將事故篩選、排行、趨勢、摘要、原始資料及地圖標記拆到 `analysis/service.py`。
- [x] 精簡 `web_server.py`，由事故 analysis service 回傳分析 API 結果。
- [ ] 視部署環境決定是否加入舊版 `.xls` 轉檔器。
- [x] 建立事故簡報 `payload_builder.py`，移除兩支 generator 內重複的統計邏輯。
- [x] 讓新式與傳統 generator 共用版本化事故統計 payload。
- [ ] 將 PPTX 物件搜尋、文字填值、表格填值與輸出抽到共用 helper。
- [ ] 建立事故分析專用的 `slide-builder.mjs` 與 `template-config.mjs`。
- [ ] 將投影片程序呼叫由 `web_server.py` 移到事故 presentation service。
- [ ] 為 `major_violation` 建立與事故分析一致的模組介面。
- [ ] 待兩套模板資料契約穩定後，再合併模板建構共用流程。
- [x] 補上 transformer 與 analysis service 單元測試。
- [ ] 補上 TOKEN 完整性測試及 PPTX 版面回歸測試。

## 簡報生成

- [x] 在網頁加入「新式版本／傳統版本」模板選擇。
- [x] 讓傳統版本的總體、路段、路口、肇因、時段、年齡及車種圖表由程式重新繪製。
- [x] 地圖維持人工置入，不納入離線自動生成流程。
- [ ] 建立兩套模板的完整必填欄位與物件名稱檢查。
