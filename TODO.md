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
- [x] 將字型、圖表、文字填值及 PPTX 物件操作抽到共用 helper。
- [x] 拆分新式程式建構與傳統模板填值 builder，保留兩套獨立版面流程。
- [x] 補上兩套 PPTX 的頁數、尺寸、圖片、表格及圖表框結構回歸測試。
- [ ] 在固定 PowerPoint／LibreOffice 渲染環境加入 PDF 或 PNG 視覺快照比對。
- [x] 將投影片程序呼叫由 `web_server.py` 移到事故 presentation service。
- [x] 為 `major_violation` 建立資料、分類規則與統計服務介面。
- [x] 將 `major_violation` 接入多檔上傳、Session 與網頁分析畫面。
- [x] 補上 transformer 與 analysis service 單元測試。
- [x] 建立傳統 PPTX 模板契約與生成前驗證，鎖定 TOKEN、圖表框及表格尺寸。

## 部署與多人使用

- [x] 將全域 Session dict 抽成具鎖定、TTL 與容量上限的可替換儲存介面。
- [x] 統一網頁與一鍵工具的 Python 虛擬環境使用規則。
- [x] 補上後端 logging、中文下載檔名與前端舊請求取消。
- [x] 將前端 API、圖表、地圖與投影片流程拆成獨立模組。
- [ ] 製作可交付其他承辦人的離線安裝包，預載公開 Python 套件。
- [ ] 若改為多人共用主機：加入持久化 Session、帳號權限、稽核紀錄、HTTPS 與備份政策。

## 簡報生成

- [x] 在網頁加入「新式版本／傳統版本」模板選擇。
- [x] 讓傳統版本的總體、路段、路口、肇因、時段、年齡及車種圖表由程式重新繪製。
- [x] 地圖維持人工置入，不納入離線自動生成流程。
- [x] 建立傳統模板必填 TOKEN／物件結構檢查及新式版面結構測試。
