# TrafficDataAnalyzer 專案結構

```text
TrafficDataAnalyzer/
├── core/
│   └── excel/
│       ├── models.py       # 所有 Excel reader 的統一資料契約
│       ├── source_detector.py
│       ├── worksheet_reader.py
│       └── pivot_cache_reader.py
├── frontend/
│   ├── index.html          # 頁面骨架與 tab panel
│   ├── styles.css          # 全域樣式
│   ├── modules.js          # 頂層資料分析模組註冊表
│   ├── app.js              # 前端狀態、事件與分析畫面協調
│   ├── api.js              # fetch、取消舊請求與錯誤解析
│   ├── chart.js            # 回應式 Canvas 圖表
│   ├── map.js              # Leaflet 標記地圖
│   ├── slides.js           # 投影片下載流程
│   └── lib/                # Leaflet 與地圖套件
├── web_server.py           # localhost HTTP API、單檔／多檔上傳與模組路由
├── package.json            # Node runtime、依賴版本與語法檢查
├── extract_pivot_cache.py  # 舊一鍵工具相容入口
├── build_xlsx.mjs          # 共用 Excel 輸出工具，保留 xls/xlsm 流程
├── modules/
│   ├── accident_analysis/
│   │   ├── data/
│   │   │   └── transformer.py      # 通用 Excel 資料 → AccidentDataset
│   │   ├── analysis/
│   │   │   └── service.py          # 篩選、排行、趨勢、摘要、原始資料、地圖標記
│   │   ├── presentation/
│   │   │   ├── payload_builder.py          # 共用、版本化的事故簡報資料契約
│   │   │   ├── service.py                  # 模板選擇、Node subprocess 與 PPTX 輸出
│   │   │   ├── presentation_generator.mjs
│   │   │   ├── traditional_presentation_generator.mjs
│   │   │   ├── build_skeleton_autofill_template.mjs
│   │   │   └── build_clean_template.mjs
│   │   ├── templates/
│   │   │   ├── 板橋分局交通事故分析週報_骨架自動填值模板.pptx
│   │   │   └── 板橋分局骨架模板_自動填值欄位對照.txt
│   │   └── README.md
│   └── major_violation/
│       ├── data/                  # 多檔標準化與可稽核匯出
│       ├── analysis/
│       │   ├── rules.py           # 重大違規／行人路權嚴格口徑
│       │   └── service.py         # 期間、趨勢與排行
│       └── README.md
├── *.txt                   # 共用使用說明
├── generated/              # 本機生成檔，不提交 Git
└── tmp/                    # 暫存資料，不提交 Git
```

## 建議的模組邊界

```text
Excel → source detector → worksheet / Pivot Cache reader
                                      ↓
                      accident transformer → AccidentDataset
                                      ↓
                               session / service
                                      ├→ 排行、趨勢、摘要、原始資料、地圖標記
                                      ├→ 前端表格／圖表／地圖元件
                                      └→ presentation payload builder
                                                     ├→ 新式 generator
                                                     └→ 傳統 generator
```

資料讀取入口位於 `core/excel/`，只負責辨識 Excel 資料來源。事故模組的 `data/transformer.py` 將通用資料轉為不可變的 `AccidentDataset`；`analysis/service.py` 集中處理事故篩選、排行、趨勢、摘要、原始資料分頁與地圖標記。`presentation/payload_builder.py` 將共用統計整理成版本化 JSON，兩支 generator 只處理各自的模板物件、圖表樣式及輸出；`presentation/service.py` 負責 Node 程序及檔案生命週期。重大違規模組透過獨立的多檔上傳 API 建立 `ViolationDataset` 與分析服務 Session，前端保留每份來源的匯入狀態。`web_server.py` 只保留上傳、Session 查找與 HTTP 回應。

`core/session_store.py` 目前提供適合每台電腦各自使用的記憶體實作，已處理多執行緒存取、TTL 與容量上限。若未來改成多位承辦人連線同一服務，應在相同介面下改接持久化儲存，並同時補上身分驗證、權限、稽核與傳輸加密。

## Git 維護建議

- `main`：可運作版本。
- `feature/<name>`：新增功能。
- 每次修改前先 `git status`，完成後執行語法檢查與 localhost 測試再提交。
- 模板與程式分開提交，避免一次 commit 混入大量生成檔。
