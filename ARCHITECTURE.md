# TrafficDataAnalyzer 專案結構

```text
TrafficDataAnalyzer/
├── frontend/
│   ├── index.html          # 頁面骨架與 tab panel
│   ├── styles.css          # 全域樣式
│   ├── modules.js          # 頂層資料分析模組註冊表
│   ├── app.js              # 前端狀態、事件與分析畫面
│   └── lib/                # Leaflet 與地圖套件
├── web_server.py           # localhost API、session、資料分析與 PPTX 呼叫
├── extract_pivot_cache.py  # 從 xlsm 還原 Pivot Cache 資料
├── presentation_generator.mjs
│                           # 套用模板、填值、重繪第五頁時段圖表
├── build_*.mjs             # Excel/PPT 模板建置工具
├── *.pptx                  # 正式模板資產
├── *.txt                   # 使用說明與欄位對照
├── generated/              # 本機生成檔，不提交 Git
└── tmp/                    # 暫存資料，不提交 Git
```

## 建議的模組邊界

```text
資料載入 → session/data adapter → 分析模組 → 共用表格/圖表/地圖元件
                                      └→ 投影片輸出模組
```

目前先完成最小可維護版本：sidebar 使用模組註冊表，事故分析仍集中在既有 `app.js` / `web_server.py`。下一階段可將每個分析項目拆成 `frontend/features/accident/`，後端則拆成 `analysis/`、`api/`、`presentation/`。

## Git 維護建議

- `main`：可運作版本。
- `feature/<name>`：新增功能。
- 每次修改前先 `git status`，完成後執行語法檢查與 localhost 測試再提交。
- 模板與程式分開提交，避免一次 commit 混入大量生成檔。
