# TrafficDataAnalyzer

本機端交通資料分析工具。現階段支援：

- 讀取一般工作表的 `.xlsx`、`.xlsm`
- 自動比較一般工作表與 Pivot Cache，使用欄位較完整的資料來源
- 事故資料的路段、路口、時段、肇因、年齡與車種分析
- 趨勢表、圖表、事故標記地圖與摘要
- 使用 Python 生成可編輯的交通事故分析週報 PPTX（新式／傳統配色）
- 清除目前 session，回到未載入狀態
- 多份重大違規 Excel 的標準化、分類、排行與趨勢分析
- 重大違規週報績效：由使用者另行上傳「績效目標值」Excel，再依所隊、違規類別與起迄日計算達成值及單頁投影片

目前仍是「每位使用者在自己的電腦啟動 localhost」的離線工具。Session 已透過可替換、具執行緒鎖定的儲存層管理；未來若改成多人共用同一台主機，可換成磁碟或資料庫實作，但在加入帳號、權限、稽核紀錄與 HTTPS 前，不應直接開放區網存取。

## 啟動

先建立虛擬環境並安裝公開 Python 套件：

```bash
./安裝Python依賴.command
./啟動網頁版.command
```

或執行：

```bash
.venv/bin/python web_server.py
```

瀏覽器開啟 `http://127.0.0.1:8765`。

## 開發檢查

執行 `.venv/bin/python -m unittest discover -v` 檢查核心與匯出功能。前端 JavaScript 為瀏覽器原生模組，無需 Node.js 建置工具。

## 目錄與模組化

頂層 sidebar 不直接寫死功能，改由 `frontend/modules.js` 的模組註冊表產生。未來新增「人口資料分析」或其他資料模組時，只需新增模組設定與對應 view，再逐步抽離該模組的分析邏輯。

詳細說明請見 [ARCHITECTURE.md](ARCHITECTURE.md)。事故專用工具與模板位於 `modules/accident_analysis/`；重大違規模組位於 `modules/major_violation/`，可在網頁一次選取多份 Excel。跨檔資料目前保留原始列、不自動去重。

## 注意事項

- 一般原始資料沒有「件數」欄位時，每列自動按 1 件計算；彙整資料保留「件數」欄加總。
- 舊版 `.xls` 請先在 Excel 另存為 `.xlsx` 或 `.xlsm`。
- 原始 Excel 與 PPT 模板不放入版本控制；請依個資與機關資料規範管理。
- Python 套件版本記錄於 `requirements.txt`；`.venv/` 不應提交。
- 生成檔請放入 `generated/`，測試與暫存檔請放入 `tmp/`。
