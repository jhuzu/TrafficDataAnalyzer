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
│   ├── app.js              # 前端狀態、事件與分析畫面
│   └── lib/                # Leaflet 與地圖套件
├── web_server.py           # localhost API、session 與模組路由
├── extract_pivot_cache.py  # 舊一鍵工具相容入口
├── build_xlsx.mjs          # 共用 Excel 輸出工具，保留 xls/xlsm 流程
├── modules/
│   ├── accident_analysis/
│   │   ├── presentation/
│   │   │   ├── presentation_generator.mjs
│   │   │   ├── build_skeleton_autofill_template.mjs
│   │   │   └── build_clean_template.mjs
│   │   ├── templates/
│   │   │   ├── 板橋分局交通事故分析週報_骨架自動填值模板.pptx
│   │   │   └── 板橋分局骨架模板_自動填值欄位對照.txt
│   │   └── README.md
│   └── major_violation/
│       └── README.md
├── *.txt                   # 共用使用說明
├── generated/              # 本機生成檔，不提交 Git
└── tmp/                    # 暫存資料，不提交 Git
```

## 建議的模組邊界

```text
Excel → source detector → worksheet / Pivot Cache reader → 統一資料契約
                                                          ↓
                                              session → 分析模組
                                                          ├→ 共用表格／圖表／地圖元件
                                                          └→ 投影片輸出模組
```

資料讀取入口已抽到 `core/excel/`。一般工作表與 Pivot Cache 都輸出相同的 `headers`、`rows`、`sourceType`、`rowMode`、`sheetName` 與 `warnings`；事故基礎分析仍集中在既有 `app.js` / `web_server.py`，下一階段再拆成事故模組自己的 `data/transformer.py` 與 `analysis/service.py`。

## Git 維護建議

- `main`：可運作版本。
- `feature/<name>`：新增功能。
- 每次修改前先 `git status`，完成後執行語法檢查與 localhost 測試再提交。
- 模板與程式分開提交，避免一次 commit 混入大量生成檔。
